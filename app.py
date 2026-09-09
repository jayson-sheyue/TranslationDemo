"""A hands-on FastAPI demo for Cloud Translation API v3.

This project deliberately keeps credentials on the server.  The browser only talks
to this application, which uses Application Default Credentials to call Google.
"""

from __future__ import annotations

import base64
import csv
import io
import mimetypes
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
ASSETS = ROOT / "assets"
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
DEFAULT_LOCATION = os.getenv("TRANSLATION_LOCATION", "us-central1").strip()
GCS_UPLOAD_MAX_BYTES = 10 * 1024 * 1024
ASSET_META = {
    "glossary/product-terms.csv": {
        "id": "glossary-product-terms",
        "kind": "glossary",
        "title": "产品术语表示例",
        "note": "表头必须是语言代码。description 列只给本地预览看，一键上传到 GCS 时会自动去掉，避免被当成第三种语言。",
        "gcs_object": "glossary/product-terms.csv",
        "language_codes": "en,zh-CN",
        "needs_gcs": True,
    },
    "glossary/test-input.txt": {
        "id": "glossary-test-input",
        "kind": "text",
        "title": "术语表测试原文",
        "note": "先不填术语表翻一次，再填 product-terms 对比 Atlas、Helios Console 等词。",
        "needs_gcs": False,
    },
    "adaptive/support-style.tsv": {
        "id": "adaptive-dataset",
        "kind": "adaptive-dataset",
        "title": "客服文风数据集",
        "note": "两列、Tab 分隔、不要表头。左列英文，右列人工确认的中文。",
        "gcs_object": "adaptive/support-style.tsv",
        "needs_gcs": True,
    },
    "adaptive/test-sentences.txt": {
        "id": "adaptive-test-input",
        "kind": "text",
        "title": "自适应数据集测试原文",
        "note": "和 TSV 里的句子相近但不完全相同，用来观察领域说法有没有带上。",
        "needs_gcs": False,
    },
    "adaptive/ticket-pairs.json": {
        "id": "adaptive-ticket",
        "kind": "adaptive-inline",
        "title": "工单（ticket）内嵌句对",
        "note": "一词多义示例：NMT 常译成故障报告，自适应可译成工单。",
        "needs_gcs": False,
    },
    "adaptive/pr-pairs.json": {
        "id": "adaptive-pr",
        "kind": "adaptive-inline",
        "title": "PR（合并请求）内嵌句对",
        "note": "NMT 可能把 PR 当成新闻稿；自适应会按开发语境理解。",
        "needs_gcs": False,
    },
    "text/html-sample.html": {
        "id": "text-html",
        "kind": "html",
        "title": "HTML 样例",
        "note": "MIME 请选 text/html。标签会尽量保留，只翻译可见文字。",
        "needs_gcs": False,
    },
    "batch/messages.txt": {
        "id": "batch-text",
        "kind": "batch-text",
        "title": "批量文本样例",
        "note": "先一键上传到你自己的 GCS，再把 gs:// 地址填进批量文本任务。",
        "gcs_object": "batch/messages.txt",
        "needs_gcs": True,
    },
}


def _import_translate():
    """Import lazily so the page can still explain setup before dependencies exist."""
    try:
        from google.cloud import translate_v3 as translate
    except ImportError as exc:  # pragma: no cover - depends on local installation
        raise HTTPException(
            status_code=503,
            detail="未安装 google-cloud-translate。请先执行 pip install -r requirements.txt。",
        ) from exc
    return translate


def _parent(location: str | None = None) -> str:
    if not PROJECT_ID:
        raise HTTPException(
            status_code=503,
            detail=(
                "尚未设置 GOOGLE_CLOUD_PROJECT。复制 .env.example 并配置项目 ID；"
                "同时使用 Application Default Credentials 完成认证。"
            ),
        )
    return f"projects/{PROJECT_ID}/locations/{location or DEFAULT_LOCATION}"


def _client():
    return _import_translate().TranslationServiceClient()


def _labels(value: dict[str, str] | None) -> dict[str, str]:
    """Accept only simple billing labels; invalid keys fail before reaching Google."""
    if not value:
        return {}
    clean: dict[str, str] = {}
    for key, item in value.items():
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,62}", key):
            raise HTTPException(422, detail=f"无效标签键：{key}")
        clean[key] = str(item)[:63]
    return clean


def _model(parent: str, model: str | None, custom_model_id: str | None) -> str | None:
    if custom_model_id:
        return f"{parent}/models/{custom_model_id.strip()}"
    if model and model != "default":
        return f"{parent}/models/{model}"
    return None


def _google_error(exc: Exception) -> HTTPException:
    # Do not expose credentials; the message normally includes useful IAM/location hints.
    return HTTPException(status_code=502, detail=f"Cloud Translation API 调用失败：{exc}")


def _storage_client():
    try:
        from google.cloud import storage
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="未安装 google-cloud-storage。请先执行 pip install -r requirements.txt。",
        ) from exc
    return storage.Client()


def _parse_gs_uri(uri: str) -> tuple[str, str]:
    raw = (uri or "").strip()
    if not raw.startswith("gs://"):
        raise HTTPException(422, detail="GCS 地址必须以 gs:// 开头，例如 gs://your-bucket/glossary/product-terms.csv")
    rest = raw[5:]
    bucket, _, blob = rest.partition("/")
    if not bucket or not blob or ".." in blob.split("/"):
        raise HTTPException(422, detail="请同时填写桶名和对象路径，例如 gs://your-bucket/glossary/product-terms.csv")
    return bucket, blob


def _asset_path(relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or any(part == ".." for part in rel.parts):
        raise HTTPException(400, detail="无效的本地样例路径。")
    path = (ASSETS / rel).resolve()
    if not str(path).startswith(str(ASSETS.resolve())) or not path.is_file():
        raise HTTPException(404, detail=f"找不到本地样例：{relative}")
    return path


def _preview_table(relative: str, text: str) -> dict[str, list[list[str]]] | None:
    suffix = Path(relative).suffix.lower()
    if suffix not in {".csv", ".tsv"}:
        return None
    dialect = csv.excel_tab if suffix == ".tsv" else csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect=dialect))
    if not rows:
        return {"headers": [], "rows": []}
    if suffix == ".csv":
        return {"headers": rows[0], "rows": rows[1:]}
    return {"headers": ["源语言", "目标语言"], "rows": rows}


def _asset_by_id(asset_id: str) -> tuple[str, dict[str, Any]]:
    for relative, meta in ASSET_META.items():
        if meta.get("id") == asset_id:
            return relative, meta
    raise HTTPException(404, detail=f"找不到本地样例：{asset_id}")


def _normalize_bucket(value: str | None) -> str | None:
    raw = (value or "").strip()
    if raw.startswith("gs://"):
        raw = raw[5:]
    raw = raw.strip("/")
    if not raw:
        return None
    if "/" in raw or ".." in raw:
        raise HTTPException(422, detail="桶名不要带对象路径。对象请写在目标 URI 里，例如 gs://your-bucket/glossary/product-terms.csv")
    return raw


def _resolve_destination(
    destination_uri: str | None,
    bucket: str | None,
    object_name: str | None,
    fallback_object: str,
) -> str:
    if destination_uri and destination_uri.strip():
        return destination_uri.strip()
    name = (object_name or fallback_object).lstrip("/")
    if not name or ".." in Path(name).parts:
        raise HTTPException(422, detail="无效的对象路径。")
    bkt = _normalize_bucket(bucket)
    if not bkt:
        raise HTTPException(422, detail="请填写目标 GCS URI，或填写你自己项目里的桶名。")
    return f"gs://{bkt}/{name}"


def _bytes_for_gcs(relative: str, data: bytes, *, glossary: bool | None = None) -> bytes:
    meta = ASSET_META.get(relative) or {}
    is_glossary = glossary if glossary is not None else meta.get("kind") == "glossary"
    suffix = Path(relative).suffix.lower() or ".csv"
    if not is_glossary or suffix != ".csv":
        return data
    text = data.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return data
    headers = [cell.strip() for cell in rows[0]]
    drop = {i for i, name in enumerate(headers) if name.casefold() == "description"}
    if not drop:
        return data
    keep = [i for i in range(len(headers)) if i not in drop]
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    for row in rows:
        writer.writerow([row[i] if i < len(row) else "" for i in keep])
    return out.getvalue().encode("utf-8")


def _asset_payload(relative: str) -> dict[str, Any]:
    path = _asset_path(relative)
    text = path.read_text(encoding="utf-8")
    meta = dict(ASSET_META.get(relative) or {"id": relative, "kind": "file", "title": path.name})
    return {
        **meta,
        "path": relative,
        "filename": path.name,
        "bytes": path.stat().st_size,
        "text": text,
        "table": _preview_table(relative, text),
    }


def _put_gcs_bytes(destination_uri: str, data: bytes, content_type: str) -> dict[str, Any]:
    if len(data) > GCS_UPLOAD_MAX_BYTES:
        raise HTTPException(413, detail="上传文件不能超过 10MB。")
    bucket_name, blob_name = _parse_gs_uri(destination_uri)
    try:
        blob = _storage_client().bucket(bucket_name).blob(blob_name)
        blob.upload_from_string(data, content_type=content_type)
    except HTTPException:
        raise
    except Exception as exc:
        raise _google_error(exc) from exc
    return {"destination_uri": f"gs://{bucket_name}/{blob_name}", "bytes": len(data)}


TRANSLATION_LLM_MODELS = {"general/translation-llm", "general/translation-llm-adaptive"}
ADAPTIVE_LLM_MODEL = "general/translation-llm-adaptive"
ADAPTIVE_LLM_TRANSLATE_HINT = (
    "TranslateText 不接受 general/translation-llm-adaptive。"
    "官方对照表里有这个 ID，但 translateText 的 model 只认 general/nmt、general/translation-llm，"
    "以及 AutoML / translation-llm-custom/{id}。"
    "自适应翻译请到「自适应翻译」页，调用 adaptiveMtTranslate（内嵌句对或数据集），不要走本页。"
)
TRANSLATION_LLM_LANGUAGES_URL = (
    "https://cloud.google.com/translate/docs/languages#translation-llm_supported_languages"
)
VISION_SYNC_MAX_BYTES = 20 * 1024 * 1024


def _is_translation_llm(model: str | None) -> bool:
    return (model or "") in TRANSLATION_LLM_MODELS


def _ocr_kind(filename: str | None, content_type: str | None, content: bytes) -> Literal["pdf", "image"]:
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    name = (filename or "").lower()
    if mime in {"application/pdf", "application/x-pdf"}:
        return "pdf"
    if mime.startswith("image/"):
        return "image"
    if name.endswith(".pdf") or content.startswith(b"%PDF"):
        return "pdf"
    guessed = (mimetypes.guess_type(filename or "")[0] or "").lower()
    if guessed == "application/pdf":
        return "pdf"
    if guessed.startswith("image/") or name.endswith(
        (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".heic")
    ):
        return "image"
    raise HTTPException(
        422,
        detail="仅支持图片或 PDF。PDF 仅处理前 5 页；更大的 PDF 请使用 GCS 异步 OCR。",
    )


def _vision_text(response: Any) -> str:
    annotation = getattr(response, "full_text_annotation", None)
    return (getattr(annotation, "text", None) or "").strip()


def _require_source_for_glossary(source_language_code: str | None, glossary_id: str | None) -> None:
    if (glossary_id or "").strip() and not (source_language_code or "").strip():
        raise HTTPException(
            status_code=422,
            detail=(
                "使用术语表时必须填写源语言，例如 en。"
                "输入框里浅灰色的 en 只是示例，不会提交。"
            ),
        )


class TextRequest(BaseModel):
    contents: list[str] = Field(min_length=1, max_length=100)
    source_language_code: str | None = None
    target_language_code: str
    mime_type: Literal["text/plain", "text/html"] = "text/plain"
    model: str | None = "general/nmt"
    custom_model_id: str | None = None
    glossary_id: str | None = None
    location: str | None = None
    labels: dict[str, str] | None = None


class DetectRequest(BaseModel):
    content: str = Field(min_length=1)
    mime_type: Literal["text/plain", "text/html"] = "text/plain"
    location: str | None = None
    labels: dict[str, str] | None = None


class LanguagesRequest(BaseModel):
    display_language_code: str = "zh-CN"
    model: str | None = "general/nmt"
    location: str | None = None


class RomanizeRequest(BaseModel):
    contents: list[str] = Field(min_length=1)
    source_language_code: str
    location: str | None = None


class BatchTextRequest(BaseModel):
    input_uri: str = Field(pattern=r"^gs://")
    output_uri_prefix: str = Field(pattern=r"^gs://")
    source_language_code: str
    target_language_codes: list[str] = Field(min_length=1, max_length=10)
    mime_type: Literal["text/plain", "text/html"] = "text/plain"
    model: str | None = "general/nmt"
    location: str | None = None
    labels: dict[str, str] | None = None


class BatchDocumentRequest(BaseModel):
    input_uri: str = Field(pattern=r"^gs://")
    output_uri_prefix: str = Field(pattern=r"^gs://")
    source_language_code: str | None = None
    target_language_codes: list[str] = Field(min_length=1, max_length=10)
    location: str | None = None
    model: str | None = "general/nmt"


class GlossaryCreateRequest(BaseModel):
    glossary_id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,62}$")
    input_uri: str = Field(pattern=r"^gs://")
    language_codes: list[str] = Field(min_length=2)
    location: str | None = None


class GlossaryDeleteRequest(BaseModel):
    location: str | None = None


class AdaptiveRequest(BaseModel):
    dataset_id: str
    content: str = Field(min_length=1)
    location: str | None = None


class ReferencePair(BaseModel):
    source_sentence: str = Field(min_length=1, max_length=512)
    target_sentence: str = Field(min_length=1, max_length=512)


class AdaptiveInlineRequest(BaseModel):
    content: str = Field(min_length=1)
    source_language_code: str
    target_language_code: str
    reference_pairs: list[ReferencePair] = Field(min_length=1, max_length=100)
    location: str | None = None


class AdaptiveFileRequest(BaseModel):
    input_uri: str = Field(pattern=r"^gs://")
    location: str | None = None


class DatasetRequest(BaseModel):
    dataset_id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,62}$")
    display_name: str = Field(min_length=1, max_length=128)
    source_language_code: str
    target_language_code: str
    location: str | None = None


class DatasetDeleteRequest(BaseModel):
    location: str | None = None


class GlossaryStopwordRequest(BaseModel):
    terms: list[str] = Field(min_length=1, max_length=100)


class GcsUploadRequest(BaseModel):
    asset_id: str | None = None
    destination_uri: str | None = None
    bucket: str | None = None
    object_name: str | None = None


# A small documented "un" sample, not a replacement for Google's full
# language-specific tables. The linked official stopwords page is canonical.
DOCUMENTED_GENERAL_STOPWORDS = {
    "the", "of", "to", "in", "for", "is", "on", "that", "by", "with", "this", "be",
    "www", "are", "as", "i", "from", "a", "com", "an", "about", "was", "edu", "who",
    "what", "where", "when", "why", "how", "which", "en", "&", "*", "and",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title="Cloud Translation API v3 Lab", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/readme")
def readme() -> FileResponse:
    return FileResponse(ROOT / "README.md", media_type="text/markdown")


@app.get("/learning-guide")
def learning_guide() -> FileResponse:
    return FileResponse(ROOT / "learning_guide.md", media_type="text/markdown")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "project_configured": bool(PROJECT_ID),
        "project_id": PROJECT_ID or None,
        "default_location": DEFAULT_LOCATION,
        "api": "Cloud Translation Advanced (v3)",
        "assets_available": ASSETS.is_dir(),
    }


@app.get("/api/assets")
def list_assets() -> dict[str, Any]:
    return {
        "assets": [_asset_payload(relative) for relative in ASSET_META],
        "bucket_placeholder": "your-bucket",
    }


@app.post("/api/assets/upload")
def upload_bundled_asset(body: GcsUploadRequest) -> dict[str, Any]:
    if not body.asset_id:
        raise HTTPException(422, detail="请指定要上传的本地样例 asset_id。")
    relative, meta = _asset_by_id(body.asset_id)
    path = _asset_path(relative)
    data = _bytes_for_gcs(relative, path.read_bytes())
    dest = _resolve_destination(body.destination_uri, body.bucket, body.object_name, meta.get("gcs_object") or path.name)
    content_type = mimetypes.guess_type(path.name)[0] or "text/plain"
    result = _put_gcs_bytes(dest, data, content_type)
    return {
        **result,
        "asset_id": meta["id"],
        "stripped_description": meta.get("kind") == "glossary" and path.suffix.lower() == ".csv",
    }


@app.post("/api/assets/upload-file")
async def upload_local_file(
    destination_uri: str | None = Form(None),
    bucket: str | None = Form(None),
    object_name: str | None = Form(None),
    strip_glossary_description: bool = Form(False),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    filename = Path(file.filename or "upload.bin").name
    if not filename or filename in {".", ".."} or "/" in filename or "\\" in filename:
        raise HTTPException(422, detail="请选择一个本地文件。")
    data = await file.read()
    data = _bytes_for_gcs(filename, data, glossary=strip_glossary_description)
    dest = _resolve_destination(destination_uri, bucket, object_name, filename)
    content_type = file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    result = _put_gcs_bytes(dest, data, content_type)
    return {**result, "filename": filename, "stripped_description": strip_glossary_description}


@app.post("/api/translate")
def translate_text(body: TextRequest) -> dict[str, Any]:
    _require_source_for_glossary(body.source_language_code, body.glossary_id)
    if (body.model or "") == ADAPTIVE_LLM_MODEL and not body.custom_model_id:
        raise HTTPException(status_code=422, detail=ADAPTIVE_LLM_TRANSLATE_HINT)
    parent = _parent(body.location)
    try:
        request: dict[str, Any] = {
            "parent": parent,
            "contents": body.contents,
            "target_language_code": body.target_language_code,
            "mime_type": body.mime_type,
            "labels": _labels(body.labels),
        }
        if body.source_language_code:
            request["source_language_code"] = body.source_language_code
        model = _model(parent, body.model, body.custom_model_id)
        if model:
            request["model"] = model
        if body.glossary_id:
            request["glossary_config"] = {
                "glossary": f"{parent}/glossaries/{body.glossary_id}",
            }
        response = _client().translate_text(request=request)
        translations = response.glossary_translations or response.translations
        return {
            "translations": [
                {
                    "translated_text": item.translated_text,
                    "detected_language_code": item.detected_language_code or None,
                    "model": item.model or None,
                    "glossary_config": bool(body.glossary_id),
                }
                for item in translations
            ],
            "request_parent": parent,
            "labels": _labels(body.labels),
            "labels_note": "标签已随请求发给 Cloud Translation，用于结算报表；Google 不会把它写进译文。此处为 Demo 回显。",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise _google_error(exc) from exc


@app.post("/api/detect")
def detect_language(body: DetectRequest) -> dict[str, Any]:
    parent = _parent(body.location)
    try:
        response = _client().detect_language(
            request={
                "parent": parent,
                "content": body.content,
                "mime_type": body.mime_type,
                "labels": _labels(body.labels),
            }
        )
        return {
            "languages": [
                {"language_code": item.language_code, "confidence": item.confidence}
                for item in response.languages
            ]
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise _google_error(exc) from exc


@app.post("/api/languages")
def list_languages(body: LanguagesRequest) -> dict[str, Any]:
    if _is_translation_llm(body.model):
        raise HTTPException(
            status_code=422,
            detail=(
                "GetSupportedLanguages 只能按 NMT 或 AutoML 模型查询语言，不支持 Translation LLM。"
                "把 general/translation-llm 传给该接口会返回 501 LLM models are not supported；"
                "这不是鉴权失败，也不代表 LLM 不能翻译。"
                f"请查看官方语言表：{TRANSLATION_LLM_LANGUAGES_URL} ；"
                "LLM 应通过 TranslateText 使用。"
            ),
        )
    parent = _parent(body.location)
    try:
        request: dict[str, Any] = {
            "parent": parent,
            "display_language_code": body.display_language_code,
        }
        model = _model(parent, body.model, None)
        if model:
            request["model"] = model
        response = _client().get_supported_languages(request=request)
        return {
            "languages": [
                {"language_code": lang.language_code, "display_name": lang.display_name,
                 "support_source": lang.support_source, "support_target": lang.support_target}
                for lang in response.languages
            ]
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise _google_error(exc) from exc


@app.post("/api/romanize")
def romanize(body: RomanizeRequest) -> dict[str, Any]:
    parent = _parent(body.location)
    try:
        response = _client().romanize_text(
            request={"parent": parent, "contents": body.contents,
                     "source_language_code": body.source_language_code}
        )
        return {"romanizations": [item.romanized_text for item in response.romanizations]}
    except HTTPException:
        raise
    except Exception as exc:
        raise _google_error(exc) from exc


@app.post("/api/batch/text")
def batch_text(body: BatchTextRequest) -> dict[str, Any]:
    parent = _parent(body.location)
    try:
        request: dict[str, Any] = {
            "parent": parent,
            "source_language_code": body.source_language_code,
            "target_language_codes": body.target_language_codes,
            "input_configs": [{"gcs_source": {"input_uri": body.input_uri}, "mime_type": body.mime_type}],
            "output_config": {"gcs_destination": {"output_uri_prefix": body.output_uri_prefix}},
            "labels": _labels(body.labels),
        }
        model = _model(parent, body.model, None)
        if model:
            request["models"] = {target: model for target in body.target_language_codes}
        operation = _client().batch_translate_text(request=request)
        return {"operation": operation.operation.name, "status": "已提交", "output_uri_prefix": body.output_uri_prefix}
    except HTTPException:
        raise
    except Exception as exc:
        raise _google_error(exc) from exc


@app.post("/api/batch/document")
def batch_document(body: BatchDocumentRequest) -> dict[str, Any]:
    parent = _parent(body.location)
    try:
        request: dict[str, Any] = {
            "parent": parent,
            "target_language_codes": body.target_language_codes,
            "input_configs": [{"gcs_source": {"input_uri": body.input_uri}}],
            "output_config": {"gcs_destination": {"output_uri_prefix": body.output_uri_prefix}},
        }
        if body.source_language_code:
            request["source_language_code"] = body.source_language_code
        model = _model(parent, body.model, None)
        if model:
            request["models"] = {target: model for target in body.target_language_codes}
        operation = _client().batch_translate_document(request=request)
        return {"operation": operation.operation.name, "status": "已提交", "output_uri_prefix": body.output_uri_prefix}
    except HTTPException:
        raise
    except Exception as exc:
        raise _google_error(exc) from exc


@app.post("/api/document")
async def document_translate(
    file: UploadFile = File(...),
    target_language_code: str = Form(...),
    source_language_code: str | None = Form(None),
    location: str | None = Form(None),
    glossary_id: str | None = Form(None),
    model: str | None = Form("general/nmt"),
    custom_model_id: str | None = Form(None),
) -> dict[str, Any]:
    _require_source_for_glossary(source_language_code, glossary_id)
    if custom_model_id and not (source_language_code or "").strip():
        raise HTTPException(422, detail="使用自定义模型时必须填写源语言。")
    if (model or "") == ADAPTIVE_LLM_MODEL or (model or "").endswith("translation-llm"):
        raise HTTPException(
            422,
            detail=(
                "TranslateDocument 不支持 Translation LLM / 自适应模型。"
                "官方文档列出的内置模型只有 general/nmt；自定义模型请填已训练的 AutoML 模型 ID。"
            ),
        )
    parent = _parent(location)
    content = await file.read()
    if not content:
        raise HTTPException(422, detail="上传的文件为空。")
    mime_type = file.content_type or mimetypes.guess_type(file.filename or "")[0]
    if not mime_type:
        raise HTTPException(422, detail="无法识别文件 MIME 类型，请上传 DOCX、PDF、PPTX 或 XLSX。")
    try:
        request: dict[str, Any] = {
            "parent": parent,
            "target_language_code": target_language_code,
            "document_input_config": {"content": content, "mime_type": mime_type},
        }
        if source_language_code:
            request["source_language_code"] = source_language_code
        resolved_model = _model(parent, model, custom_model_id)
        if resolved_model:
            request["model"] = resolved_model
        if glossary_id:
            request["glossary_config"] = {"glossary": f"{parent}/glossaries/{glossary_id}"}
        response = _client().translate_document(request=request)
        document = response.document_translation
        outputs = [base64.b64encode(output).decode("ascii") for output in document.byte_stream_outputs]
        return {
            "detected_language_code": document.detected_language_code or None,
            "mime_type": document.mime_type or mime_type,
            "model": resolved_model or f"{parent}/models/general/nmt",
            "files_base64": outputs,
            "warning": "输出为 Base64；页面可下载。生产环境的大文件请使用批量文档翻译。",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise _google_error(exc) from exc


def _glossary_summary(item: Any) -> dict[str, Any]:
    name = item.name
    languages = list(item.language_codes_set.language_codes)
    if not languages:
        pair = item.language_pair
        languages = [code for code in (pair.source_language_code, pair.target_language_code) if code]
    return {"id": name.rsplit("/", 1)[-1], "name": name, "languages": languages}


@app.get("/api/glossaries")
def list_glossaries(location: str | None = None) -> dict[str, Any]:
    try:
        parent = _parent(location)
        glossaries = _client().list_glossaries(parent=parent)
        return {"location": parent, "glossaries": [_glossary_summary(item) for item in glossaries]}
    except HTTPException:
        raise
    except Exception as exc:
        raise _google_error(exc) from exc


@app.post("/api/glossaries")
def create_glossary(body: GlossaryCreateRequest) -> dict[str, Any]:
    parent = _parent(body.location)
    try:
        translate = _import_translate()
        glossary = translate.Glossary(
            name=f"{parent}/glossaries/{body.glossary_id}",
            language_codes_set=translate.Glossary.LanguageCodesSet(language_codes=body.language_codes),
            input_config=translate.GlossaryInputConfig(gcs_source=translate.GcsSource(input_uri=body.input_uri)),
        )
        operation = _client().create_glossary(parent=parent, glossary=glossary)
        return {"operation": operation.operation.name, "status": "已提交", "glossary": glossary.name}
    except HTTPException:
        raise
    except Exception as exc:
        raise _google_error(exc) from exc


@app.delete("/api/glossaries/{glossary_id}")
def delete_glossary(glossary_id: str, body: GlossaryDeleteRequest) -> dict[str, Any]:
    try:
        operation = _client().delete_glossary(name=f"{_parent(body.location)}/glossaries/{glossary_id}")
        return {"operation": operation.operation.name, "status": "删除已提交"}
    except HTTPException:
        raise
    except Exception as exc:
        raise _google_error(exc) from exc


@app.post("/api/glossaries/validate-stopwords")
def validate_glossary_stopwords(body: GlossaryStopwordRequest) -> dict[str, Any]:
    ignored = [term for term in body.terms if term.strip().casefold() in DOCUMENTED_GENERAL_STOPWORDS]
    return {
        "ignored_if_exact_match": ignored,
        "checked": body.terms,
        "note": "这是官方通用（un）列表中的示例预检；其他语言的完整停止词请以官方文档为准。",
    }


@app.post("/api/adaptive/translate")
def adaptive_translate(body: AdaptiveRequest) -> dict[str, Any]:
    parent = _parent(body.location)
    try:
        # adaptiveMtTranslate is intentionally separate from TranslateText. It uses a dataset,
        # while the Translation LLM adaptive model can also select similar examples server-side.
        response = _client().adaptive_mt_translate(
            request={
                "parent": parent,
                "dataset": f"{parent}/adaptiveMtDatasets/{body.dataset_id}",
                "content": [body.content],
            }
        )
        return {"translations": [item.translated_text for item in response.translations]}
    except HTTPException:
        raise
    except Exception as exc:
        raise _google_error(exc) from exc


def _nmt_baseline(content: str, source: str, target: str, location: str | None) -> str | None:
    """Best-effort NMT comparison so Adaptive MT's often-subtle effect is visible."""
    try:
        parent = _parent(location)
        response = _client().translate_text(
            request={
                "parent": parent,
                "contents": [content],
                "source_language_code": source,
                "target_language_code": target,
                "mime_type": "text/plain",
                "model": f"{parent}/models/general/nmt",
            }
        )
        return response.translations[0].translated_text
    except Exception:
        return None


@app.post("/api/adaptive/translate-inline")
def adaptive_translate_inline(body: AdaptiveInlineRequest) -> dict[str, Any]:
    """Adaptive MT with request-scoped parallel examples, no persistent dataset."""
    pairs = [pair.model_dump() for pair in body.reference_pairs]
    try:
        response = _client().adaptive_mt_translate(
            request={
                "parent": _parent(body.location),
                "content": [body.content],
                "reference_sentence_config": {
                    "source_language_code": body.source_language_code,
                    "target_language_code": body.target_language_code,
                    "reference_sentence_pair_lists": [{"reference_sentence_pairs": pairs}],
                },
            }
        )
        translations = [item.translated_text for item in (response.glossary_translations or response.translations)]
        nmt = _nmt_baseline(body.content, body.source_language_code, body.target_language_code, body.location)
        return {
            "translations": translations,
            "language_code": response.language_code,
            "nmt_baseline": nmt,
            "used_reference_pairs": pairs,
            "note": (
                "句对已随请求发给 Adaptive MT，不是被忽略了。"
                "它会轻度借鉴领域说法，但不会照抄脏话/极端口语，也不会像术语表那样强制替换专有名词。"
                "请对比 translations 与 nmt_baseline；短句上两者经常几乎一样。"
            ),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise _google_error(exc) from exc


@app.get("/api/adaptive/datasets")
def list_datasets(location: str | None = None) -> dict[str, Any]:
    try:
        parent = _parent(location)
        datasets = _client().list_adaptive_mt_datasets(parent=parent)
        return {"datasets": [{"name": d.name, "display_name": d.display_name,
                               "source": d.source_language_code, "target": d.target_language_code}
                              for d in datasets]}
    except HTTPException:
        raise
    except Exception as exc:
        raise _google_error(exc) from exc


@app.post("/api/adaptive/datasets")
def create_dataset(body: DatasetRequest) -> dict[str, Any]:
    try:
        parent = _parent(body.location)
        dataset = _import_translate().AdaptiveMtDataset(
            name=f"{parent}/adaptiveMtDatasets/{body.dataset_id}",
            display_name=body.display_name,
            source_language_code=body.source_language_code,
            target_language_code=body.target_language_code,
        )
        result = _client().create_adaptive_mt_dataset(parent=parent, adaptive_mt_dataset=dataset)
        return {"status": "已创建", "dataset": result.name, "display_name": result.display_name}
    except HTTPException:
        raise
    except Exception as exc:
        raise _google_error(exc) from exc


@app.delete("/api/adaptive/datasets/{dataset_id}")
def delete_dataset(dataset_id: str, body: DatasetDeleteRequest) -> dict[str, Any]:
    try:
        _client().delete_adaptive_mt_dataset(name=f"{_parent(body.location)}/adaptiveMtDatasets/{dataset_id}")
        return {"status": "已删除"}
    except HTTPException:
        raise
    except Exception as exc:
        raise _google_error(exc) from exc


@app.get("/api/adaptive/datasets/{dataset_id}/files")
def list_dataset_files(dataset_id: str, location: str | None = None) -> dict[str, Any]:
    try:
        parent = f"{_parent(location)}/adaptiveMtDatasets/{dataset_id}"
        files = _client().list_adaptive_mt_files(parent=parent)
        return {"files": [{"name": item.name, "display_name": item.display_name,
                           "entry_count": item.entry_count} for item in files]}
    except HTTPException:
        raise
    except Exception as exc:
        raise _google_error(exc) from exc


@app.post("/api/adaptive/datasets/{dataset_id}/files")
def import_dataset_file(dataset_id: str, body: AdaptiveFileRequest) -> dict[str, Any]:
    try:
        parent = f"{_parent(body.location)}/adaptiveMtDatasets/{dataset_id}"
        response = _client().import_adaptive_mt_file(
            request={"parent": parent, "gcs_input_source": {"input_uri": body.input_uri}}
        )
        item = response.adaptive_mt_file
        return {"status": "已导入", "file": item.name, "display_name": item.display_name,
                "entry_count": item.entry_count}
    except HTTPException:
        raise
    except Exception as exc:
        raise _google_error(exc) from exc


@app.delete("/api/adaptive/datasets/{dataset_id}/files/{file_id}")
def delete_dataset_file(dataset_id: str, file_id: str, body: DatasetDeleteRequest) -> dict[str, Any]:
    try:
        name = f"{_parent(body.location)}/adaptiveMtDatasets/{dataset_id}/adaptiveMtFiles/{file_id}"
        _client().delete_adaptive_mt_file(name=name)
        return {"status": "已删除该文件导入的所有句对"}
    except HTTPException:
        raise
    except Exception as exc:
        raise _google_error(exc) from exc


@app.post("/api/image-translate")
async def image_translate(
    file: UploadFile = File(...),
    target_language_code: str = Form("zh-CN"),
    source_language_code: str | None = Form(None),
) -> dict[str, Any]:
    """Optional extension: Vision OCR (image or a small PDF) then v3 translation."""
    content = await file.read()
    if not content:
        raise HTTPException(422, detail="上传的文件为空。")
    if len(content) > VISION_SYNC_MAX_BYTES:
        raise HTTPException(422, detail="同步 OCR 最大 20MB。更大的 PDF 请放到 GCS，使用 Vision 的异步 OCR。")
    kind = _ocr_kind(file.filename, file.content_type, content)
    try:
        from google.cloud import vision
        client = vision.ImageAnnotatorClient()
        pages_processed: int | None = None

        if kind == "pdf":
            # Synchronous files:annotate accepts inline bytes and, if pages is omitted,
            # annotates the first five pages. Listing 1–5 would break 1-page PDFs.
            # Longer scans need asyncBatchAnnotateFiles with a GCS URI.
            batch_response = client.batch_annotate_files(
                requests=[
                    vision.AnnotateFileRequest(
                        input_config=vision.InputConfig(content=content, mime_type="application/pdf"),
                        features=[vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)],
                    )
                ]
            )
            if not batch_response.responses:
                raise HTTPException(502, detail="Vision PDF OCR 未返回任何页面结果。")
            file_response = batch_response.responses[0]
            if file_response.error.message:
                raise HTTPException(502, detail=f"Vision PDF OCR 失败：{file_response.error.message}")
            page_errors = [
                page.error.message
                for page in file_response.responses
                if getattr(page.error, "message", "")
            ]
            if page_errors and not any(_vision_text(page) for page in file_response.responses):
                raise HTTPException(502, detail=f"Vision PDF OCR 失败：{page_errors[0]}")
            extracted = "\n\n".join(filter(None, (_vision_text(page) for page in file_response.responses)))
            pages_processed = len(file_response.responses)
        else:
            vision_response = client.document_text_detection(image=vision.Image(content=content))
            if vision_response.error.message:
                raise HTTPException(502, detail=f"Vision OCR 失败：{vision_response.error.message}")
            extracted = _vision_text(vision_response)

        if not extracted:
            raise HTTPException(422, detail="未检测到可翻译的文字。")
        result = translate_text(TextRequest(
            contents=[extracted], source_language_code=source_language_code,
            target_language_code=target_language_code,
        ))
        return {
            "ocr_text": extracted,
            "translation": result["translations"][0]["translated_text"],
            "input_type": kind,
            "pages_processed": pages_processed,
            "note": (
                "本地 PDF OCR 最多处理前 5 页；如需全部页面或大文件，请使用 Vision 的 GCS 异步 OCR。"
                if kind == "pdf" else None
            ),
        }
    except HTTPException:
        raise
    except ImportError as exc:
        raise HTTPException(503, detail="图片 / PDF OCR 需要 google-cloud-vision：pip install -r requirements.txt") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Cloud Vision / Translation 调用失败：{exc}") from exc
