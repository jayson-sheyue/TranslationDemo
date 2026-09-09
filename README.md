# Cloud Translation API v3 Lab：零基础使用说明

这是一个中文 Web Demo。它把 Google Cloud Translation **Advanced（v3）** 的能力做成可以点的页面：输入文字、点按钮、看结果。

如果你是第一次接触 Google Cloud，请不要一上来研究“模型、区域、IAM、GCS”这些名词。正确顺序是：

1. 先让页面完成一次普通文本翻译；
2. 再根据自己的工作场景选择功能；
3. 最后才使用术语表、批量翻译和自适应翻译。

> 这是真实 API，不是演示数据。每次点击翻译都会从服务器向 Google Cloud 发出请求，可能产生费用。请只用无敏感的测试内容开始。

## 30 秒：我该用哪一个功能？

| 你想做的事 | 点哪里 | 适合的情况 | 暂时不要用在 |
| --- | --- | --- | --- |
| 翻一两句聊天、评论、按钮文案 | 文本翻译 → NMT | 要快、内容短 | 强制产品名译法 |
| 翻客服邮件、营销内容、较正式文案 | 文本翻译 → Translation LLM | 比 NMT 更重视表达质量 | 没有先做基础质量对比 |
| 不知道原文是哪种语言 | 检测与语言 | 用户上传/输入的内容来源不确定 | 只有几个字的短句（可能猜错） |
| 产品名、品牌、行业词必须固定 | 术语表 | `Atlas` 必须总是译成“阿特拉斯” | 想自动修正整段翻译 |
| 翻一份小 PDF、DOCX、PPTX、XLSX | 批量与文档 → 在线文档 | 想立即下载译文 | 很大或很多份文件 |
| 翻很多文本/文档文件 | 批量与文档 → 批量 | 文件已在 GCS | 本地电脑上尚未上传的文件 |
| 让译文接近公司的语气与用词 | 自适应翻译 | 有人工确认的双语好句子 | 没有可靠双语样例 |
| 看日文/韩文等文字的发音 | 扩展实验 → 罗马化 | 需要读音的拉丁字母写法 | 想知道原文含义（那是翻译） |
| 翻译图片中的文字 | 扩展实验 → 图片 OCR | 已启用 Cloud Vision API | 图片含私人/机密信息 |

## 这套 Demo 做了什么？

- `TranslateText`：普通文本和 HTML 翻译，可选 NMT、Translation LLM、Adaptive LLM 和自定义 AutoML 模型；
- `DetectLanguage` 与 `GetSupportedLanguages`：猜测原文语言、检查模型支持什么语言；
- `RomanizeText`：把非拉丁文字写成近似发音的拉丁文字；
- `TranslateDocument`：上传一份小型 Office/PDF 文档并下载译文；
- `BatchTranslateText` 与 `BatchTranslateDocument`：对 GCS 中的许多文件发起异步任务；
- Glossary：从 GCS 导入术语表，保证关键术语一致；
- Adaptive MT：请求内参考句对、数据集、TSV/TMX 文件导入与管理；
- 可选图片 OCR：先用 Cloud Vision 识别文字，再交给 Translation API。

## 在开始前，你需要的四样东西

把下面四项想成“打开水龙头”前必须接好的水管：

1. **Google Cloud 项目**：资源和账单都归属到一个项目中。
2. **已启用结算**：Translation API 是按使用量收费的服务。
3. **启用 Cloud Translation API**：在 Cloud Console 搜索并启用它。
4. **身份凭据（ADC）**：让这台服务器有权调用 API。浏览器本身不会拿到凭据。

图片实验额外需要 Cloud Vision API。Glossary、批量和自适应数据集还需要 Cloud Storage（GCS）。

## 快速开始：复制这些命令

以下命令适用于 macOS / Linux 终端。`YOUR_PROJECT_ID` 必须替换为你自己的 Google Cloud 项目 ID；不要保留尖括号。

```bash
cd /Users/apple/Desktop/Demo/TranslationDemo

# 第一次运行时创建 Python 虚拟环境并安装依赖
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 登录 Google Cloud，生成本机开发用的 Application Default Credentials（ADC）
gcloud auth application-default login

# 指定你要使用的 Google Cloud 项目和默认区域
export GOOGLE_CLOUD_PROJECT="YOUR_PROJECT_ID"
export TRANSLATION_LOCATION="us-central1"

# 启动页面
uvicorn app:app --reload --port 8000
```

然后在浏览器打开 <http://127.0.0.1:8000>。

Windows PowerShell 的两行环境变量写法：

```powershell
$env:GOOGLE_CLOUD_PROJECT="YOUR_PROJECT_ID"
$env:TRANSLATION_LOCATION="us-central1"
```

### 我怎么知道配置成功？

页面右上角会显示其中一种状态：

- **“已配置项目：xxx”**：可以开始文本翻译。
- **“等待配置 GOOGLE_CLOUD_PROJECT”**：还没有设置项目 ID；回到上面的 `export` 命令。
- **页面返回 401 / 403 错误**：项目或 API 找到了，但登录身份没有权限；看下面的“常见错误”。

## 第一次练习：翻译一句话

1. 打开页面的“从这里开始”。
2. 点“去做第一次翻译”。
3. 保留默认内容、目标语言 `zh-CN` 和模型 `general/nmt`。
4. 点“翻译”。
5. 深色结果框出现译文，即代表最重要的基础路径已经可用。

建议先把英文 `Hello, Cloud Translation API!` 翻成简体中文。不要第一步就上传文件、创建术语表或修改模型 ID。

## 初学者必须知道的名词

| 名词 | 用人话解释 | 什么时候才需要关心 |
| --- | --- | --- |
| API | 一个程序向另一个服务请求结果的方式 | 页面按钮在后台就是调用 API |
| 项目 ID | 你的 Google Cloud 资源“所属账户夹”名称 | 启动服务时必须设置 |
| ADC | 服务器向 Google 证明“我是谁”的登录凭据 | 本地首次启动时必须执行登录 |
| IAM | 谁可以做什么的权限系统 | 遇到 403，或部署到生产时 |
| GCS / Cloud Storage | Google Cloud 的文件存储，地址以 `gs://` 开头 | 术语表、批量任务和自适应数据集 |
| 区域 / location | Google 存放和处理某些资源的位置 | 用 Glossary / 数据集 / 批量时 |
| 模型 | 翻译引擎的不同版本/策略 | 基础翻译成功后再比较 |
| 长时间运行任务 | 提交后不会马上完成的后台任务 | 批量翻译和创建 Glossary |

## 模型怎么选：不要只选“听起来最强”的

### NMT：默认的起点

`general/nmt` 速度快，适合聊天、界面按钮、评论、短客服消息等实时内容。第一次练习永远从它开始。

### Translation LLM：重视自然表达时再比较

`general/translation-llm` 适合对语气、可读性、营销文案等更敏感的内容。正确用法是：拿同一段文本分别用 NMT 和 LLM 翻译，请母语读者看效果，再衡量延迟与成本。

### Adaptive Translation：你有优质样例时

若你手里已有人工确认的“原文 + 目标译文”句对，可用它引导用词和语气。它不是把差的机器翻译反复喂进去就会变好的训练工具。

### AutoML 自定义模型：最后再考虑

这是更重的长期投入，需要准备较多领域数据、训练并维护模型。大多数新项目先用 LLM + Glossary + Adaptive Translation 就够了。

## 功能的具体使用提醒

### 普通文字与 HTML

- 普通文字选 `text/plain`。
- 内容确实包含 HTML 标签时才选 `text/html`；服务会翻译标签中间的可见文字，尽量保留标签。
- 不要把 XML 当作 HTML 传入。
- 知道源语言时就填写，例如英文 `en`、日文 `ja`。自动检测适合未知语言，不适合极短或混杂句子。

### 术语表

术语表是“小词典”，不是自动审校员。请把已审核的关键词放进去，并使用完整、有意义的短语。`the`、`and` 这类单独常用词会被忽略。

术语表的资源区域必须与翻译请求兼容。新手不知道用什么时，先统一使用 `us-central1`。

### 文档与批量

- 上传一份小文档，使用在线文档翻译；Demo 将返回可下载的文件。
- 要处理一批文件，使用 Batch；输入、输出都必须是 `gs://` 地址。
- Batch 返回的是 operation 名称，不是最终文件。你需要稍后在 Cloud Console 的 Operations 和 GCS 输出目录查看结果。
- 批量文本输入支持 `.txt`、`.html`、`.tsv`，需 UTF-8；一次最多 100 文件、最多 10 个目标语言，总量最多 100M Unicode code points。

### 自适应翻译

- **临时测试**：在页面填内嵌参考句对。它们只用于这一次请求。
- **长期复用**：创建数据集，再从 GCS 导入 TSV/TMX 双语句对。
- 请使用人工确认的双语样例；不相关、低质量或自相矛盾的样例会降低效果。

## 权限：最小权限原则

不要给任何账号“管理员”就图省事。建议：

- 在线翻译、检测、语言清单、罗马化、在线文档：`roles/cloudtranslate.user`。
- 创建/删除 Glossary：`roles/cloudtranslate.editor`。
- 读取批量输入、Glossary 文件和自适应数据文件：按所需 bucket 配 `roles/storage.objectViewer`。
- 写批量输出：按所需 bucket 配 `roles/storage.objectCreator`。

部署到 Cloud Run、GKE、Compute Engine 时，优先使用工作负载绑定的服务账号，不要把长期服务账号 JSON 放入仓库、前端、镜像或聊天记录。

## 成本与安全：第一次使用也要看

1. 所有翻译请求可能产生费用；先用短句测试。
2. 给 Google Cloud 项目设置 Budget 和费用告警。
3. 用页面中的 `labels` 标记团队或环境，例如 `{"team":"support","environment":"dev"}`，方便日后排查成本。
4. 不要翻译密码、访问令牌、身份证信息、病历、未公开合同或其他无权发送给 Google Cloud 的内容。
5. 此 Demo 不提供面向最终用户的登录功能。若部署到公网，应增加 IAP、企业 SSO 或应用层登录、速率限制和审计日志。

## 常见错误：按现象排查

| 看到的现象 | 最可能原因 | 先做什么 |
| --- | --- | --- |
| `尚未设置 GOOGLE_CLOUD_PROJECT` | 未设置项目环境变量 | 重新执行 `export GOOGLE_CLOUD_PROJECT=...` 后重启服务 |
| `403 Permission denied` | API 未启用、ADC 登录的账号没权限、服务账号 IAM 不足 | 检查 API 已启用；执行 `gcloud auth application-default login`；确认 `roles/cloudtranslate.user` |
| `404` 或找不到术语表/数据集 | ID 错了，或区域不同 | 核对资源名、ID 和 `us-central1` 是否一致 |
| `gs://...` 相关错误 | 文件没上传 GCS，或服务账号无法读写 bucket | 确认路径、对象存在和 Storage IAM |
| 批量任务没有文件 | 任务仍在运行，或看的不是输出前缀 | 用 operation 名称到 Operations 查看；打开指定输出目录 |
| 译文不符合产品用词 | 只靠默认模型无法保证专有词 | 创建并测试 Glossary；再考虑自适应样例 |
| 页面能打开、按钮却失败 | 服务端没有 ADC 或项目配置 | 看终端错误，并重新做“快速开始” |

## 开发与验证

不调用 Google Cloud 的静态检查：

```bash
python3 -m py_compile app.py
node --check static/app.js
```

启动后，可打开 `http://127.0.0.1:8000/api/health` 查看项目配置。完整的练习步骤、GCS 样例和场景化决策，请继续看 [learning_guide.md](learning_guide.md)。

## 项目结构

```text
app.py                 FastAPI 路由与 Google v3 客户端调用
static/index.html      中文网页与新手引导
static/app.js          表单、场景跳转、结果与下载逻辑
static/styles.css      响应式样式
learning_guide.md      从第一次翻译到高级能力的练习手册
.env.example           不含密钥的环境变量示例
requirements.txt       Python 依赖
```

## 官方文档

- [API 概览](https://docs.cloud.google.com/translate/docs/api-overview?hl=zh-cn) · [模型比较](https://docs.cloud.google.com/translate/docs/advanced/compare-models?hl=zh-cn)
- [支持语言](https://docs.cloud.google.com/translate/docs/languages?hl=zh-cn) · [支持格式](https://docs.cloud.google.com/translate/docs/supported-formats?hl=zh-cn) · [设置](https://docs.cloud.google.com/translate/docs/setup?hl=zh-cn)
- [文本翻译](https://docs.cloud.google.com/translate/docs/translate-text?hl=zh-cn) · [检测语言](https://docs.cloud.google.com/translate/docs/detect-language?hl=zh-cn&usertype=Advanced) · [列出支持语言](https://docs.cloud.google.com/translate/docs/list-supported-languages?hl=zh-cn&usertype=Advanced)
- [批量翻译](https://docs.cloud.google.com/translate/docs/advanced/batch-translation?hl=zh-cn) · [文档翻译](https://docs.cloud.google.com/translate/docs/advanced/translate-documents?hl=zh-cn) · [术语表](https://docs.cloud.google.com/translate/docs/advanced/glossary?hl=zh-cn)
- [罗马化](https://docs.cloud.google.com/translate/docs/advanced/romanize-text?hl=zh-cn) · [停止词](https://docs.cloud.google.com/translate/docs/advanced/stopwords?hl=zh-cn) · [混合术语表教程](https://docs.cloud.google.com/translate/docs/hybrid-glossaries-tutorial?hl=zh-cn)
- [自适应翻译](https://docs.cloud.google.com/translate/docs/advanced/adaptive-translation?hl=zh-cn) · [自定义翻译](https://docs.cloud.google.com/translate/docs/advanced/custom-translations?hl=zh-cn) · [管理自适应数据](https://docs.cloud.google.com/translate/docs/advanced/adaptive-translation-data?hl=zh-cn)
