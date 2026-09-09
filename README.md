# Cloud Translation API v3 Lab

一个中文界面的 Python / FastAPI Web Demo，用真实的 **Cloud Translation - Advanced (v3)** 客户端库演示下列能力：

- `TranslateText`：纯文本、HTML、自动检测语言、NMT、Translation LLM、Adaptive LLM、AutoML 模型、用户标签和术语表；
- `DetectLanguage`、`GetSupportedLanguages` 和预览版 `RomanizeText`；
- `BatchTranslateText`、在线 `TranslateDocument` 与 `BatchTranslateDocument`；
- 术语表的创建、列出、删除和翻译时套用；
- Adaptive MT 的请求内参考句对，以及数据集创建、列出、删除、GCS 文件导入、文件列举/删除和 `AdaptiveMtTranslate`；
- 参考“混合术语表”教程的可选图片 OCR（Cloud Vision）→ 翻译扩展；
- AutoML 自定义 NMT 模型的调用入口（模型训练本身在 AutoML Translation 中完成）。

> 这不是 mock。每个运行按钮都会从服务器端调用 Google Cloud。未配置凭据时，页面会显示明确的配置错误，而不会返回伪造结果。

## 快速开始

前置条件：Python 3.10+、已启用结算的 Google Cloud 项目，以及 Cloud Translation API。图片实验还需 Cloud Vision API。

```bash
cd /Users/apple/Desktop/Demo/TranslationDemo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 任选一种 ADC 方式：本地用户登录，或服务账号 JSON（勿提交 JSON 文件）
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT="YOUR_PROJECT_ID"
export TRANSLATION_LOCATION="us-central1"
uvicorn app:app --reload --port 8000
```

打开 <http://127.0.0.1:8000>。PowerShell 请使用 `$env:GOOGLE_CLOUD_PROJECT="YOUR_PROJECT_ID"`。

也可从 `.env.example` 复制环境变量。此示例刻意不自动读取 `.env`，避免将本地密钥惯性带进生产。

## 最小 IAM 与 Storage 权限

- 仅在线翻译、检测、语言清单、罗马化、文档翻译：`roles/cloudtranslate.user`。
- 创建或删除术语表 / 管理长任务：`roles/cloudtranslate.editor`。
- 批量翻译、批量文档和从 GCS 创建术语表：服务账号还需要输入对象读取与输出对象写入权限；按 bucket 绑定 `roles/storage.objectViewer` 与 `roles/storage.objectCreator`（或经审查的等效最小权限）。
- 图片扩展：另加 Cloud Vision 对应调用权限。

不要把服务账号 JSON 放入 `static/`、浏览器表单、git 或镜像层。Web 应用以服务账号运行时，优先采用 Workload Identity / 附加服务账号，而非长期 JSON 密钥。

## 功能与 API 映射

| 页面实验 | v3 方法 | 关键要求 |
| --- | --- | --- |
| 文本翻译 | `TranslateText` | `text/plain` 或 `text/html`；LLM 仅使用纯文本 |
| 语言检测 / 清单 | `DetectLanguage` / `GetSupportedLanguages` | 指定模型可获得对应模型支持的语言 |
| 罗马化 | `RomanizeText` | Preview；不是翻译 |
| 批量文本 | `BatchTranslateText` | GCS；`.txt`、`.html`、`.tsv`；异步 |
| 在线 / 批量文档 | `TranslateDocument` / `BatchTranslateDocument` | PDF、Office 等；保持格式；后者为异步 GCS 任务 |
| 术语表 | `CreateGlossary` / `ListGlossaries` / `DeleteGlossary` | 从 GCS CSV/TSV/TMX 导入；术语表与调用位置必须一致 |
| 自适应 | `Create/List/DeleteAdaptiveMtDataset`、`Import/List/DeleteAdaptiveMtFile`、`AdaptiveMtTranslate` | 请求内参考句对或导入 TSV/TMX 后使用 |

## 运行说明和限制

1. **区域必须一致。** Glossary、批量和文档演示默认 `us-central1`。如果改区域，应让术语表、数据集、模型、父资源和请求保持兼容。不能把资源名称从另一个区域直接粘贴过来。
2. **长时间运行操作。** 页面提交 batch 或 Glossary 后只返回 operation name；请在 Cloud Console / Operations 中观察完成状态和 GCS 输出。不要让 HTTP 请求等待任务完成。Adaptive MT 数据集与文件导入接口是同步的。
3. **在线文档。** Demo 为方便演示把结果以 Base64 返回并触发下载，适合小文件。生产大文件使用 `BatchTranslateDocument`，避免占用 Web 进程内存。
4. **HTML。** v3 翻译 HTML 时翻译标签之间的文字、尽量保留标签；XML 不受支持。Translation LLM 文本模式应使用 `text/plain`。
5. **模型。** `general/nmt` 适合低延迟；`general/translation-llm` 强调质量；`general/translation-llm-adaptive` 使用参考数据。AutoML 自定义模型通过完整的 v3 model resource 调用。不同模型支持语言不同，先用“检测与语言”验证。
6. **术语表。** 在“术语表”创建成功后，将 ID 填到“文本翻译”的 Glossary ID。页面的停止词预检只覆盖官方通用（`un`）列表示例；单独的无效搜索词（例如英文 `the`、`and`）会被忽略，完整语言列表以官方文档为准。
7. **成本和配额。** 翻译按字符、模型和操作计费；设置预算/配额并为请求使用 labels。批量文本一次最多 100 个文件、10 个目标语言、总计最多 100M Unicode code points，UTF-8 编码。

## 目录

```text
app.py                 FastAPI 路由与 Google v3 客户端调用
static/index.html      中文演示界面
static/app.js          表单、结果和下载逻辑
static/styles.css      响应式样式
learning_guide.md      按实验推进的学习路径和诊断清单
.env.example           安全的配置示例
requirements.txt       Python 依赖
```

## 验证

不需 Google 凭据的静态检查：

```bash
python3 -m py_compile app.py
uvicorn app:app --port 8000
curl http://127.0.0.1:8000/api/health
```

完成凭据配置后，在 UI 依次执行：文本翻译 → 语言检测 → 语言清单 → 罗马化。之后再用专用的测试 GCS bucket 尝试术语表、批量文本和批量文档。

## 官方资料

- [Cloud Translation API 概览](https://docs.cloud.google.com/translate/docs/api-overview?hl=zh-cn)
- [模型选择](https://docs.cloud.google.com/translate/docs/advanced/compare-models?hl=zh-cn)
- [支持的语言](https://docs.cloud.google.com/translate/docs/languages?hl=zh-cn) 与 [支持的格式](https://docs.cloud.google.com/translate/docs/supported-formats?hl=zh-cn)
- [设置](https://docs.cloud.google.com/translate/docs/setup?hl=zh-cn)、[文本翻译](https://docs.cloud.google.com/translate/docs/translate-text?hl=zh-cn)、[批量翻译](https://docs.cloud.google.com/translate/docs/advanced/batch-translation?hl=zh-cn)
- [文档翻译](https://docs.cloud.google.com/translate/docs/advanced/translate-documents?hl=zh-cn)、[术语表](https://docs.cloud.google.com/translate/docs/advanced/glossary?hl=zh-cn)
- [自适应翻译](https://docs.cloud.google.com/translate/docs/advanced/adaptive-translation?hl=zh-cn)、[自适应数据集](https://docs.cloud.google.com/translate/docs/advanced/adaptive-translation-data?hl=zh-cn)、[自定义翻译](https://docs.cloud.google.com/translate/docs/advanced/custom-translations?hl=zh-cn)
