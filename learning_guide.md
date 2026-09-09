# Cloud Translation API v3 练习手册

这是一份给第一次接触 Google Cloud 的人的动手教程。它不假设你知道 API、IAM、GCS、模型或命令行。

请按顺序完成。每一节都有：**什么时候用、要填什么、预期看到什么、常见误解**。

## 练习前的安全规则

- 用自己写的测试文字，例如 `Hello world`，不要用真实客户对话、合同、病历、密码、token 或私人照片。
- 每次 API 调用可能收费。先用几句话，不要一开始就跑批量任务。
- 这个 Web Demo 的服务器使用 Google Cloud 凭据；浏览器不保存凭据。若部署到公网，务必额外做登录和访问控制。
- 如果你只是想翻一句话，做到练习 1 就可以停，不必学习 GCS、术语表和自适应翻译。

## 练习 0：先把“能不能调用 Google”确认清楚

### 你要完成什么

让页面右上角显示“已配置项目”。这只说明项目 ID 已设置；真正的权限会在第一次翻译时验证。

### 一次性准备

在项目目录中执行：

```bash
source .venv/bin/activate
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT="YOUR_PROJECT_ID"
export TRANSLATION_LOCATION="us-central1"
uvicorn app:app --reload --port 8000
```

打开 <http://127.0.0.1:8000>。

### 每个命令在做什么

| 命令 | 用人话解释 | 是否每次都要做 |
| --- | --- | --- |
| `source .venv/bin/activate` | 让终端使用本项目的 Python 包 | 每开一个新终端时 |
| `gcloud auth application-default login` | 在本机登录 Google，给程序一张“调用 API 的通行证” | 首次或登录过期时 |
| `export GOOGLE_CLOUD_PROJECT=...` | 告诉程序费用和资源属于哪个项目 | 每开一个新终端时，除非写到环境配置 |
| `export TRANSLATION_LOCATION=us-central1` | 给需要区域的资源一个统一默认位置 | 建议每次设置 |
| `uvicorn ...` | 启动网页服务 | 每次要使用 Demo 时 |

### 如果失败

- 没有 `gcloud` 命令：先安装 Google Cloud CLI。
- 不知道项目 ID：在 Google Cloud Console 顶部项目选择器中查看；它不是项目名称。
- 第一次翻译报 `403`：确认已启用 Cloud Translation API，并给登录账号/服务账号 `roles/cloudtranslate.user`。

---

## 练习 1：第一次文本翻译

### 什么时候用

你只需要把少量文字立刻翻出来：聊天、评论、按钮、客服短消息、文章片段。

### 页面怎么填

进入“文本翻译”，使用：

| 字段 | 第一次填什么 | 为什么 |
| --- | --- | --- |
| 待翻译内容 | `Good morning!` | 无敏感、结果容易看懂 |
| 源语言 | 留空，或填 `en` | 留空会自动检测；知道是英文就填 `en` 更稳定 |
| 目标语言 | `zh-CN` | 简体中文 |
| 内容类型 | `text/plain` | 普通文字，不是网页 HTML |
| 模型 | `general/nmt` | 快、适合第一次验证 |
| 自定义模型 / 术语表 / 区域 | 全部留空 | 现在不需要增加复杂度 |

点“翻译”。结果框里应出现中文问候语。

### 再试一次：一次翻多句

在文本框每行写一句：

```text
The payment was successful.
Your order will arrive tomorrow.
```

页面会把每一行当作一条独立内容。这样你可以检查每句对应的输出。

### 常见误解

- **“为什么不是逐字翻译？”** 不同语言语序不同。质量应看整句是否自然、是否表达原意。
- **“为什么结果偶尔不同？”** 模型会随着服务更新；不要把某次完整句子输出当作永久不变的程序规则。
- **“我可以把用户所有聊天记录直接发过去吗？”** 先做数据合规评估、最小化传输内容、设置访问控制和保留策略。

---

## 练习 2：NMT 和 Translation LLM 该如何选

### 目标

用同一段文字比较，而不是凭名称猜哪个“更好”。

### 操作

1. 在文本翻译输入：`We are sorry for the delay. Your refund has been processed.`
2. 源语言填 `en`，目标填 `zh-CN`。
3. 先选 `general/nmt`，记下结果。
4. 再选 `general/translation-llm`，使用完全相同输入翻译。
5. 比较：术语是否准确、语气是否自然、响应是否足够快、成本是否可接受。

### 简单选择法

| 需求 | 首选 | 原因 |
| --- | --- | --- |
| 页面按钮、短聊天、即时回复 | NMT | 通常更适合低延迟场景 |
| 面向用户的正式邮件、营销内容 | Translation LLM | 更值得比较语言表达质量 |
| 关键产品名必须固定 | 任一基础模型 + Glossary | 模型本身不保证你的专有译法 |
| 要贴近自己公司语气 | Adaptive MT | 需要优质双语样例 |

不要为了“高级”而把所有调用都换成 LLM。先对自己的真实样本做对照评测。

---

## 练习 3：HTML 翻译和语言检测

### HTML 翻译

点击“填入 HTML 样例”。页面会自动把内容类型切到 `text/html`。

你会看到 HTML 标签（例如 `<h1>`、`<strong>`）被尽量保留，标签中的可见文字被翻译。

适合：网站片段、富文本编辑器内容。
不适合：XML、任意自定义标记语言。不要把 `text/html` 当成“能处理一切格式”的开关。

### 语言检测

进入“检测与语言”，输入：

```text
Bonjour tout le monde
```

点“检测语言”。结果会给出候选语言代码和置信度。

**什么时候要检测？** 用户上传内容、内容来自多国家、你确实不知道来源语言。
**什么时候不要检测？** 你已知原文是英文/日文，或者只有一个词。已知时直接传源语言更稳定。

### 支持语言清单

在同一页选 NMT 或 Translation LLM，点“列出支持语言”。这不是单纯的百科清单：不同模型支持的语言可能不同。上线前请先确认你的源语言和目标语言组合可用。

---

## 练习 4：术语表，让关键字保持一致

### 什么时候用

你希望某些词绝不随模型自由翻译，例如：

- 产品 `Atlas` 必须译为“阿特拉斯”；
- 行业词 `claim` 在保险场景必须译为“理赔申请”；
- 某品牌名必须保留英文。

### 你需要先理解 GCS

GCS（Google Cloud Storage）就是 Google Cloud 的文件存储。地址以 `gs://` 开头，不是电脑的 `/Users/...` 路径。

例子：

```text
gs://my-translation-demo/glossary/terms.csv
```

### 最小的术语文件样例

在电脑上新建 `terms.csv`，内容可以是：

```csv
Atlas,阿特拉斯
cloud translation,云翻译
```

上传到你已创建的 GCS bucket：

```bash
gcloud storage cp terms.csv gs://YOUR_BUCKET/glossary/terms.csv
```

然后在“术语表”页填写：

| 字段 | 示例 |
| --- | --- |
| 术语表 ID | `product-terms` |
| 输入文件 | `gs://YOUR_BUCKET/glossary/terms.csv` |
| 语言代码 | `en,zh-CN` |
| 区域 | `us-central1` |

点“创建术语表”。它是后台任务，页面会先给 operation 名称；稍后刷新清单。创建成功后，回到“文本翻译”，在“术语表 ID”填 `product-terms`，再翻译含 `Atlas` 的句子。

### 三个重要规则

1. 术语表不是全文校对工具，只控制匹配的术语。
2. 单独的 `the`、`and`、`in` 这类常见词可能被忽略；请使用有意义的短语。
3. Glossary、翻译请求必须使用兼容的区域。新手请统一用 `us-central1`。

---

## 练习 5：文档翻译和批量翻译

### A. 在线文档翻译：先试小文件

适合：你现在电脑里的一份小型、无敏感测试 DOCX/PDF/PPTX/XLSX。

1. 打开“批量与文档”。
2. 在最右侧“TranslateDocument（在线）”选择文件。
3. 目标语言填写 `zh-CN`。
4. 原文是英文就填 `en`；不知道可以留空。
5. 点“翻译并下载”。

服务会尽量保留版式，但不要承诺每一处复杂排版都完全一致。特别是 Word 文本框内容可能保留源语言；请人工检查输出。

### B. 批量文本：很多 .txt / .html / .tsv

适合：已有很多文件，且都已经放在 GCS 中。

例子：

```text
输入：gs://YOUR_BUCKET/input/messages.txt
输出：gs://YOUR_BUCKET/output/
原文：en
目标：zh-CN,ja
```

点“提交文本任务”后，不会立即返回译文。把 operation 名称记下来，到 Cloud Console 的 Operations 观察状态，再去输出目录下载结果。

### C. 批量文档：很多 Office/PDF 文件

输入可使用 GCS 通配符，例如：

```text
gs://YOUR_BUCKET/input/*.docx
```

输出必须是一个文件夹前缀，例如：

```text
gs://YOUR_BUCKET/output/
```

### 为什么我会收到 GCS 权限错误？

调用翻译的账号不仅要有 Translation 权限，还必须能读输入 bucket、写输出 bucket。常见最小角色是：

- 读输入：`roles/storage.objectViewer`
- 写输出：`roles/storage.objectCreator`

不要通过给整个项目 Owner 来解决权限错误；应只给需要的 bucket 和角色。

---

## 练习 6：自适应翻译，让风格更像你的团队

### 先问自己：我真的需要它吗？

如果你的问题只是“产品名翻错”，先用 Glossary。
如果你的问题是“同一句客服话术需要保持礼貌、简洁、固定称呼”，且你有人工认可的双语例句，再用自适应翻译。

### A. 最小实验：内嵌参考句对

进入“自适应翻译”的“以内嵌参考句对翻译”。保留样例：

```json
[{"source_sentence":"gateway timeout","target_sentence":"网关超时"}]
```

原文填写：

```text
The gateway timed out.
```

点“使用参考句对”。参考句不会被长期保存到数据集；它只影响本次请求，适合尝试。

### B. 长期使用：数据集

当你有许多优质句对时：

1. 创建数据集，确定源语言和目标语言，例如 `en` → `zh-CN`。
2. 准备 TSV 或 TMX 双语句对文件并上传到 GCS。
3. 用“导入 Adaptive MT 文件”导入。
4. 用“列出数据集文件”确认导入了多少条句对。
5. 以数据集 ID 发起翻译。

官方建议的样例要覆盖你的真实领域词汇、写法和语气。控制台使用至少 5 对，至多 10,000 对；API 上限更高，但绝不是数量越大越好。每对句子最长 512 个字符（两句合计）。

### 不要这样做

- 不要导入没有人工审核的机器翻译；
- 不要把法律、医疗、金融等高风险译文只交给模型决定；
- 不要删掉不确定的数据集文件。删除文件会移除该文件导入的所有句对。

---

## 练习 7：罗马化与图片 OCR

### 罗马化不是翻译

输入日文 `こんにちは世界`、源语言选 `ja`，罗马化结果会是近似读音的拉丁文字，例如 `Kon'nichiwa sekai`。

它回答的是“怎么念”，不是“是什么意思”。想知道含义，请用文本翻译。该能力属于 Preview，生产使用前需准备回退方案。

### 图片 OCR + 翻译

流程是：图片 → Cloud Vision 识别文字 → Cloud Translation 翻译文字。

因此需要：

1. 启用 Cloud Vision API；
2. 给调用身份 Vision 权限；
3. 使用不含私人信息的测试图片；
4. 先检查 OCR 抄出的文字是否正确，再判断翻译是否正确。

如果 OCR 已经把文字认错，Translation API 无法知道原图内容，应该先处理 OCR 问题。

---

## 上线前检查表

### 质量

- [ ] 用你的真实但脱敏的样本比较 NMT 与 Translation LLM；
- [ ] 让目标语言母语者检查重要场景；
- [ ] 用 Glossary 固定关键产品名和领域词；
- [ ] 检查文档输出的标题、表格、文本框与排版；
- [ ] 验证所选模型支持所有源/目标语言。

### 安全与权限

- [ ] 前端、代码仓库、Docker 镜像中没有服务账号 JSON、token 或 API key；
- [ ] 用服务账号 / Workload Identity，而不是长期个人凭据；
- [ ] IAM 和 GCS 都是最小权限；
- [ ] 不把 Demo 直接裸露在公网；加 IAP、SSO 或应用登录；
- [ ] 为高风险内容设计人工审核和申诉流程。

### 成本与运维

- [ ] 设置 Budget 和告警；
- [ ] 用 labels 区分开发、测试、生产和业务团队；
- [ ] 保存批量任务的 operation 名称，并异步监控完成/失败；
- [ ] 为重试设置上限，避免故障时无限重试；
- [ ] 记录所用模型、术语表版本和数据集版本，便于复现结果。

## 还需要帮助？按错误文本找答案

| 错误关键词 | 先检查 |
| --- | --- |
| `GOOGLE_CLOUD_PROJECT` | 是否设置了环境变量，并重新启动服务 |
| `Permission denied` / `403` | Cloud Translation API 是否启用；ADC 是否登录；IAM 是否有 user/editor 权限 |
| `not found` / `404` | Glossary、数据集、模型 ID 和 location 是否匹配 |
| `gs://` | bucket、对象路径、Storage 读写权限 |
| `unsupported language` | 在“检测与语言”里对相同模型查支持清单 |
| `invalid argument` | 语言代码、MIME 类型、JSON 格式、文件类型是否正确 |

## 官方文档索引

- [API 概览](https://docs.cloud.google.com/translate/docs/api-overview?hl=zh-cn) · [模型比较](https://docs.cloud.google.com/translate/docs/advanced/compare-models?hl=zh-cn) · [支持语言](https://docs.cloud.google.com/translate/docs/languages?hl=zh-cn)
- [支持格式](https://docs.cloud.google.com/translate/docs/supported-formats?hl=zh-cn) · [设置](https://docs.cloud.google.com/translate/docs/setup?hl=zh-cn) · [检测语言](https://docs.cloud.google.com/translate/docs/detect-language?hl=zh-cn&usertype=Advanced) · [列出支持语言](https://docs.cloud.google.com/translate/docs/list-supported-languages?hl=zh-cn&usertype=Advanced)
- [文本翻译](https://docs.cloud.google.com/translate/docs/translate-text?hl=zh-cn) · [批量翻译](https://docs.cloud.google.com/translate/docs/advanced/batch-translation?hl=zh-cn) · [文档翻译](https://docs.cloud.google.com/translate/docs/advanced/translate-documents?hl=zh-cn)
- [术语表](https://docs.cloud.google.com/translate/docs/advanced/glossary?hl=zh-cn) · [混合术语表教程](https://docs.cloud.google.com/translate/docs/hybrid-glossaries-tutorial?hl=zh-cn) · [罗马化](https://docs.cloud.google.com/translate/docs/advanced/romanize-text?hl=zh-cn) · [停止词](https://docs.cloud.google.com/translate/docs/advanced/stopwords?hl=zh-cn)
- [自适应翻译](https://docs.cloud.google.com/translate/docs/advanced/adaptive-translation?hl=zh-cn) · [自定义翻译](https://docs.cloud.google.com/translate/docs/advanced/custom-translations?hl=zh-cn) · [数据集管理](https://docs.cloud.google.com/translate/docs/advanced/adaptive-translation-data?hl=zh-cn)
