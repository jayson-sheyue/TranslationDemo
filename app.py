"""A hands-on FastAPI demo for Cloud Translation API v3.

This project deliberately keeps credentials on the server.  The browser only talks
to this application, which uses Application Default Credentials to call Google.
"""

from __future__ import annotations

import base64
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
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
DEFAULT_LOCATION = os.getenv("TRANSLATION_LOCATION", "us-central1").strip()


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
    }


@app.post("/api/translate")
def translate_text(body: TextRequest) -> dict[str, Any]:
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
) -> dict[str, Any]:
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
        if glossary_id:
            request["glossary_config"] = {"glossary": f"{parent}/glossaries/{glossary_id}"}
        response = _client().translate_document(request=request)
        document = response.document_translation
        outputs = [base64.b64encode(output).decode("ascii") for output in document.byte_stream_outputs]
        return {
            "detected_language_code": document.detected_language_code or None,
            "mime_type": document.mime_type or mime_type,
            "files_base64": outputs,
            "warning": "输出为 Base64；页面可下载。生产环境的大文件请使用批量文档翻译。",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise _google_error(exc) from exc


@app.get("/api/glossaries")
def list_glossaries(location: str | None = None) -> dict[str, Any]:
    try:
        parent = _parent(location)
        glossaries = _client().list_glossaries(parent=parent)
        return {"glossaries": [{"name": item.name, "languages": list(item.language_codes_set.language_codes)} for item in glossaries]}
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


@app.post("/api/adaptive/translate-inline")
def adaptive_translate_inline(body: AdaptiveInlineRequest) -> dict[str, Any]:
    """Adaptive MT with request-scoped parallel examples, no persistent dataset."""
    try:
        response = _client().adaptive_mt_translate(
            request={
                "parent": _parent(body.location),
                "content": [body.content],
                "reference_sentence_config": {
                    "source_language_code": body.source_language_code,
                    "target_language_code": body.target_language_code,
                    "reference_sentence_pair_lists": [{
                        "reference_sentence_pairs": [pair.model_dump() for pair in body.reference_pairs]
                    }],
                },
            }
        )
        translations = response.glossary_translations or response.translations
        return {"translations": [item.translated_text for item in translations],
                "language_code": response.language_code}
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
    """Optional extension from the hybrid glossary tutorial: Vision OCR then v3 translation."""
    content = await file.read()
    try:
        from google.cloud import vision
        vision_response = vision.ImageAnnotatorClient().document_text_detection(
            image=vision.Image(content=content)
        )
        if vision_response.error.message:
            raise HTTPException(502, detail=f"Vision OCR 失败：{vision_response.error.message}")
        extracted = vision_response.full_text_annotation.text.strip()
        if not extracted:
            raise HTTPException(422, detail="未在图片中检测到可翻译的文字。")
        result = translate_text(TextRequest(
            contents=[extracted], source_language_code=source_language_code,
            target_language_code=target_language_code,
        ))
        return {"ocr_text": extracted, "translation": result["translations"][0]["translated_text"]}
    except HTTPException:
        raise
    except ImportError as exc:
        raise HTTPException(503, detail="图片功能需要 google-cloud-vision：pip install -r requirements.txt") from exc
    except Exception as exc:
        raise _google_error(exc) from exc
