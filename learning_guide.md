# Cloud Translation API v3 练习手册

这是一份给第一次接触 Google Cloud 的人的动手教程。它不假设你知道 API、IAM、GCS、模型或命令行。

请按顺序完成。每一节都有：**什么时候用、要填什么、预期看到什么、常见误解**。

## 练习前的安全规则

- 用自己写的测试文字，例如 `Hello world`，不要用真实客户对话、合同、病历、密码、token 或私人照片。
- 每次 API 调用可能收费。先用几句话，不要一开始就跑批量任务。
- 这个 Web Demo 的服务器使用 Google Cloud 凭据；浏览器不保存凭据。若部署到公网，务必额外做登录和访问控制。
- 如果你只是想翻一句话，做到练习 1 就可以停，不必学习 GCS、术语表和自适应翻译。
- 术语表、数据集、批量输入的样例在仓库 `assets/` 目录。部署后页面会自动预览；需要放到 GCS 时，请填写**你自己的桶**并用页面一键上传。

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
uvicorn app:app --reload --port 8010
```

打开 <http://127.0.0.1:8010>。

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

进入“语言检测”，输入：

```text
Bonjour tout le monde
```

点“检测语言”。结果会给出候选语言代码和置信度。

**什么时候要检测？** 用户上传内容、内容来自多国家、你确实不知道来源语言。
**什么时候不要检测？** 你已知原文是英文/日文，或者只有一个词。已知时直接传源语言更稳定。

### 支持语言清单

不同模型支持的语言可能不同，上线前请先确认你的源语言和目标语言组合可用。

- 打开「语言检测」页，点“列出 NMT 支持语言”，Demo 会调用 `GetSupportedLanguages`。
- Translation LLM **不要**用这个接口查询：Google 会返回 `501 LLM models are not supported`。请打开 [Translation LLM 官方语言表](https://cloud.google.com/translate/docs/languages#translation-llm_supported_languages)。LLM 仍可通过「文本翻译」使用。

---

## 练习 4：术语表，让关键字保持一致

### 什么时候用

你希望某些词绝不随模型自由翻译，例如：

- 产品 `Atlas` 必须译为固定中文（本仓库样例定为「幻月」）；
- 行业词 `claim` 在保险场景必须译为“理赔申请”；
- 某品牌名必须保留英文。

### 你需要先理解 GCS

GCS（Google Cloud Storage）就是 Google Cloud 的文件存储。地址以 `gs://` 开头，不是电脑的 `/Users/...` 路径。

例子：

```text
gs://your-bucket/glossary/product-terms.csv
```

请使用**你自己项目**里已经创建的桶。别人的内部测试桶你读不到，这个 Demo 也不会预填任何内部地址。

### 用仓库里的术语表示例

打开「术语表」页。页面会自动加载 `assets/glossary/product-terms.csv`，用表格预览表头和词条。`description` 列只给本地阅读；点「一键上传到我的 GCS」时会被去掉。

1. 在页面填写你的桶名，例如 `your-bucket`。
2. 点术语表卡片上的「一键上传到我的 GCS」（也可以上传自己的 CSV）。
3. 创建表单里的输入文件应变成 `gs://your-bucket/glossary/product-terms.csv`。
4. 术语表 ID 用 `product-terms`，语言代码 `en,zh-CN`，区域 `us-central1`。
5. 点“创建术语表”。它是后台任务；稍后刷新清单。
6. 点样例「术语表测试原文」的「填入表单」，回到“文本翻译”，在进阶选项填 `product-terms`，源语言填 `en`。

若你更想自己建文件：表头必须是语言代码，例如：

```csv
en,zh-CN
Atlas,幻月
cloud translation,云翻译
```

也可以继续用命令行上传：

```bash
gcloud storage cp assets/glossary/product-terms.csv gs://YOUR_BUCKET/glossary/product-terms.csv
```

命令行上传不会自动去掉 `description` 列；用页面一键上传，或先删掉该列再 `gcloud storage cp`。

### 三个重要规则

1. 术语表不是全文校对工具，只控制匹配的术语。
2. 单独的 `the`、`and`、`in` 这类常见词可能被忽略；请使用有意义的短语。
3. Glossary、翻译请求必须使用兼容的区域。新手请统一用 `us-central1`。

---

## 练习 5：文档翻译和批量翻译

### A. 在线文档翻译：先试小文件

适合：你现在电脑里的一份小型、无敏感测试 DOCX/PDF/PPTX/XLSX。

1. 打开“文档翻译”。
2. 选择一份测试文件。
3. 目标语言填写 `zh-CN`。
4. 原文是英文就填 `en`；不知道可以留空。
5. 点“翻译并下载”。

服务会尽量保留版式，但不要承诺每一处复杂排版都完全一致。特别是 Word 文本框内容可能保留源语言；请人工检查输出。

### B. 批量文本：很多 .txt / .html / .tsv

适合：已有很多文件，且都已经放在**你自己的** GCS 中。仓库 `assets/batch/messages.txt` 会在「批量翻译」页自动预览，填写桶名后可一键上传。

例子：

```text
输入：gs://YOUR_BUCKET/batch/messages.txt
输出：gs://YOUR_BUCKET/batch/out/
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

页面上有两条路：**路径 A 先试 5 分钟**（不用 GCS），确认有感觉后再做 **路径 B 数据集**。

### A. 最小实验：内嵌参考句对

打开“自适应翻译”，左侧卡片已经填好工单（ticket）样例。也可以点“填入工单示例 / 填入 PR 示例”；内容来自仓库 `assets/adaptive/` 里的 JSON，部署后会自动加载。

默认原文：

```text
Please open a ticket for this outage.
```

点“用参考句翻译”。参考句不会存进数据集；只影响这一次请求。

### B. 用仓库里的客服文风数据集

仓库已经拟造了一份英文→中文客服句对：`assets/adaptive/support-style.tsv`。打开「自适应」页即可预览表格。格式要求：

- 两列，用 **Tab** 分隔（不是逗号）
- **不要表头**
- 左列原文、右列人工确认的译文
- 和术语表 `assets/glossary/product-terms.csv` 对齐了几个词：Helios Console → 赫利俄斯控制台，support specialist → 技术支持老师

#### 1. 上传到你自己的 GCS

在页面填写桶名，点数据集卡片上的「一键上传到我的 GCS」。也可以上传自己的 TSV。不要使用别人的内部测试桶。

等价命令行：

```bash
gcloud storage cp assets/adaptive/support-style.tsv gs://YOUR_BUCKET/adaptive/support-style.tsv
```

#### 2. 按页面 1–4 步点按钮（不要跳）

| 步骤 | 做什么 | 本样例填什么 |
| --- | --- | --- |
| 1 创建空数据集 | 定死语言方向 | ID `support-style`，`en` → `zh-CN` |
| 2 导入句对 | 把 GCS 文件灌进数据集 | `gs://YOUR_BUCKET/adaptive/support-style.tsv` |
| 3 确认导入 | 看文件和句对数 | 应看到约 8 条 |
| 4 用数据集翻译 | 翻**相近但不完全相同**的新句子 | 点测试原文卡片的「填入表单」，或见 `assets/adaptive/test-sentences.txt` |

第 4 步默认原文：

```text
The gateway timed out; retry succeeded.
Please retry after a few minutes.
A support specialist will contact you about the refund.
Please sign in to Helios Console.
```

把同一段再拿到“文本翻译”，用 NMT / Translation LLM 各翻一次，对比语气是不是更像客服口径。

官方建议至少 5 对、至多约 10,000 对；每对合计最长 512 字符。数量不是越大越好。导入成功后可以删 GCS 文件；以后要更新语料，需要再上传再导入。

### 不要这样做

- 不要导入没有人工审核的机器翻译；
- 不要把法律、医疗、金融等高风险译文只交给模型决定；
- 不要删掉不确定的数据集文件。删除文件会移除该文件导入的所有句对。

---

## 练习 7：罗马化与图片 OCR

### 罗马化不是翻译

输入日文 `こんにちは世界`、源语言选 `ja`，罗马化结果会是近似读音的拉丁文字，例如 `Kon'nichiwa sekai`。

它回答的是“怎么念”，不是“是什么意思”。想知道含义，请用文本翻译。该能力属于 Preview，生产使用前需准备回退方案。

### 图片 / 小型 PDF OCR + 翻译

流程是：图片或 PDF → Cloud Vision 识别文字 → Cloud Translation 翻译文字。

因此需要：

1. 启用 Cloud Vision API；
2. 给调用身份 Vision 权限；
3. 使用不含私人信息的测试图片或 PDF；
4. 先检查 OCR 抄出的文字是否正确，再判断翻译是否正确。

如果 OCR 已经把文字认错，Translation API 无法知道原图内容，应该先处理 OCR 问题。

本 Demo 的 PDF 是 Vision 的同步“文件 OCR”路径：最多处理前 5 页、最大 20MB。需要扫描长 PDF、全量页面或批量 PDF 时，必须把文件放到 GCS，使用 Vision 的异步 `asyncBatchAnnotateFiles`，结果会以 JSON 写回 GCS；这不是即时上传后立即显示结果的功能。反过来，如果 PDF 本身就有可选文字，请优先用“文档翻译”，更适合保留原版式。

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
| `unsupported language` | NMT 在“语言检测”查支持清单；LLM 看 [官方语言表](https://cloud.google.com/translate/docs/languages#translation-llm_supported_languages) |
| `501` / `LLM models are not supported` | 不要用 `GetSupportedLanguages` 查 Translation LLM；该接口只支持 NMT / AutoML |
| `invalid argument` | 语言代码、MIME 类型、JSON 格式、文件类型是否正确 |

## 官方文档索引

- [API 概览](https://docs.cloud.google.com/translate/docs/api-overview?hl=zh-cn) · [模型比较](https://docs.cloud.google.com/translate/docs/advanced/compare-models?hl=zh-cn) · [支持语言](https://docs.cloud.google.com/translate/docs/languages?hl=zh-cn)
- [GetSupportedLanguages](https://docs.cloud.google.com/translate/docs/reference/rest/v3/projects/getSupportedLanguages) · [Translation LLM](https://docs.cloud.google.com/translate/docs/translation-llm)
- [支持格式](https://docs.cloud.google.com/translate/docs/supported-formats?hl=zh-cn) · [设置](https://docs.cloud.google.com/translate/docs/setup?hl=zh-cn) · [检测语言](https://docs.cloud.google.com/translate/docs/detect-language?hl=zh-cn&usertype=Advanced) · [列出支持语言](https://docs.cloud.google.com/translate/docs/list-supported-languages?hl=zh-cn&usertype=Advanced)
- [文本翻译](https://docs.cloud.google.com/translate/docs/translate-text?hl=zh-cn) · [批量翻译](https://docs.cloud.google.com/translate/docs/advanced/batch-translation?hl=zh-cn) · [文档翻译](https://docs.cloud.google.com/translate/docs/advanced/translate-documents?hl=zh-cn)
- [术语表](https://docs.cloud.google.com/translate/docs/advanced/glossary?hl=zh-cn) · [混合术语表教程](https://docs.cloud.google.com/translate/docs/hybrid-glossaries-tutorial?hl=zh-cn) · [罗马化](https://docs.cloud.google.com/translate/docs/advanced/romanize-text?hl=zh-cn) · [停止词](https://docs.cloud.google.com/translate/docs/advanced/stopwords?hl=zh-cn)
- [自适应翻译](https://docs.cloud.google.com/translate/docs/advanced/adaptive-translation?hl=zh-cn) · [自定义翻译](https://docs.cloud.google.com/translate/docs/advanced/custom-translations?hl=zh-cn) · [数据集管理](https://docs.cloud.google.com/translate/docs/advanced/adaptive-translation-data?hl=zh-cn)
