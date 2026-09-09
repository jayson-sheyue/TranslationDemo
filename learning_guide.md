# Cloud Translation API v3 学习指南

本指南按由浅入深的实验组织。每一步都对应 Demo 中的一个页面和官方 v3 能力；先使用没有敏感信息的示例文本和专用测试 bucket。

## 0. 准备：身份、项目、区域

1. 创建独立的开发项目，启用 Cloud Translation API，并配置结算。
2. 本地执行 `gcloud auth application-default login`；部署到 Cloud Run/GKE/Compute Engine 时改用附加的服务账号。不要向前端或仓库交付密钥。
3. 赋予最少所需的 `roles/cloudtranslate.user`。管理 Glossary 时再使用 `roles/cloudtranslate.editor`。
4. 运行 `uvicorn app:app --reload --port 8000`，打开页面右上方，确认它显示项目 ID。
5. 将 `TRANSLATION_LOCATION` 设为 `us-central1` 进行 Glossary、批量、文档和数据集实验。请先检查所选模型和语言对在该区域是否受支持。

若“项目未配置”，设置 `GOOGLE_CLOUD_PROJECT`；若出现 `403`，检查 API、IAM 和 ADC 所属账号；若出现 `404`，通常是资源 ID 或位置不一致。

## 1. TranslateText：先比较模型

在“文本翻译”输入两行简短文本，源语言留空，目标设为 `zh-CN`，依次选择：

1. `general/nmt`：一般的实时、低延迟翻译；
2. `general/translation-llm`：更重视输出质量；
3. `general/translation-llm-adaptive`：适合需要示例数据适配的场景；
4. 从 AutoML Translation 获得模型后，填入自定义模型 ID 覆盖模型下拉项。

记录质量、延迟与成本差异。不要把所有内容固定交给“最佳”模型：面向用户的短实时内容往往需要 NMT 的延迟，而品牌/法律等内容可能需要更高质量或领域模型。

### HTML 实验

点“填入 HTML 样例”，选择 `text/html`，观察标签保留而标签间的可见文字被翻译。只传受支持的 HTML，**不要**把 XML 视作 HTML。Translation LLM 的文本输入使用 `text/plain`。

### Labels 实验

保留 `{"demo":"v3-lab"}`，再改为 `{"team":"support","environment":"dev"}`。标签会随 TranslateText、BatchTranslateText、DetectLanguage 进入用量/结算细分。键应以小写字母开头，后续字符使用小写字母、数字、`_` 或 `-`。

## 2. 检测与支持语言：不要硬编码假设

- 把法语、日语、夹杂多个语言的句子依次送入 `DetectLanguage`，观察候选列表与 confidence。
- 在 `GetSupportedLanguages` 中分别选择 NMT 和 Translation LLM。语言支持是**按模型**而非仅按 API 决定，应用应先校验源/目标方向。
- 自动检测很方便，但知道源语言时应显式提供，尤其是短文本、语言混杂文本和文档场景。

## 3. RomanizeText：发音转写不是翻译

在“扩展实验”中以 `ja` 输入 `こんにちは世界`。得到的是类似 `Kon'nichiwa sekai` 的拉丁文字表达，不是中文或英文含义。该功能是 Preview，应为其保留回退方案并留意发布阶段/服务条款。

## 4. Glossary：可控术语而非替换脚本

1. 在专用 GCS bucket 创建一个 CSV、TSV 或 TMX glossary 文件。使用已审校的术语对，例如 `Atlas,阿特拉斯`；服务账号需要读取该对象。
2. 在 Demo 填写 `gs://...` URI 和语言代码集，创建后等待 long-running operation 完成。
3. 刷新术语表，随后在文本翻译页填入其 ID，翻译包含 `Atlas` 的文本。
4. 保证 Glossary 与翻译请求位于相同资源位置。

### 停止词实验

不要创建只有 `the`、`and`、`in`、`www` 一类条目的英文 Glossary；它们在完全匹配时会被服务忽略。解决方法是使用更有语义的短语（如 `terms and conditions`），或把产品/领域词做成完整术语。不要企图以单字符和常用虚词操纵翻译。

## 5. 批量文本：GCS 与异步设计

1. 上传 UTF-8 `.txt`、`.html` 或 RFC 4180 兼容的 `.tsv` 到测试 bucket。
2. 在 Demo 提供输入对象 URI、输出前缀、源语言，至多 10 个目标语言。
3. 界面会马上返回 operation 名称；到 Google Cloud Console 的 Operations 和输出 GCS 前缀确认状态与结果。

批量文本一次最多处理 100 个文件，总量最多 100M Unicode code points。TSV 可有两列：可选 ID 和待翻译文本；尽量令每行不超过 10K Unicode code points。不要轮询页面来等待任务，生产系统应保存 operation name、异步跟踪并重试可恢复错误。

## 6. 文档：在线方式和批量方式

支持 DOC/DOCX、PDF、PPT/PPTX、XLS/XLSX。服务会尽量保留版式；DOC/DOCX 文本框内容不会翻译，这是验证输出时应检查的限制。

- **在线文档**：上传一个小型测试文件，选择目标语言，Demo 会返回并下载译文。适合即时、少量文档。
- **批量文档**：使用 GCS URI 或通配符与输出前缀。适合文件集和大文档，仍以 long-running operation 完成。

不要用 Web 进程内存处理生产大文件；保留 GCS 输出、操作 ID、请求者和成本标签等审计信息。

## 7. 自适应翻译：两种数据驱动路径

自定义翻译包含两种不同方案：

| 方案 | 适用场景 | 数据 / 运营 |
| --- | --- | --- |
| 自适应翻译 | 小型、高质量的示例句对；风格、语气、语态适配 | 不训练或维护模型；数据集可由相似句筛选示例 |
| AutoML Translation | 术语正确性高度关键、固定领域 | 导入更大量训练数据，训练并维护自己的模型 |

### Adaptive MT 数据集实验

1. 创建 `en` → `zh-CN` 数据集；创建是同步接口，保存返回的数据集 resource name。
2. 使用 Demo 的「导入 Adaptive MT 文件」把 GCS 中的 TSV/TMX 平行句对导入该数据集；也可列出文件和导入句对数。控制台路径要求至少 5、最多 10,000 句对；API 最多 30,000，每对合计最多 512 个字符。
3. 句对要覆盖真实领域的词汇、写法和语气，不要混入未审校的机器翻译。
4. 通过 `AdaptiveMtTranslate` 填入 dataset ID，翻译接近样例域的原文。与相同文本的 NMT / Translation LLM 输出并排评估。
5. 再尝试“以内嵌参考句对翻译”：它不写入数据集，适合一次性传入少量、明确的平行句对。它与数据集方式共享 `AdaptiveMtTranslate`，但不能同时使用两种参考来源。

每次自适应请求只翻译一个目标语言。数据集和数据文件都有列出与删除 API；删除某个文件会从数据集移除该文件带来的所有句对，删除数据集会移除其中所有数据，务必采用生产变更审批。

## 8. 图片文字：混合术语表教程的边界

Cloud Translation 不读取像素。Demo 的图片扩展先调用 Cloud Vision OCR，取得文字后再用 v3 翻译。打开此实验前启用 Vision API 和相应 IAM。OCR 不准确时，先修复文字识别结果；用术语表控制术语时，改在 Text 翻译实验中传入同样的 OCR 文本和 Glossary ID。

## 9. 发布前检查表

- [ ] 前端没有 API key、服务账号 JSON 或访问令牌；
- [ ] 采用最小 IAM 权限，GCS bucket 仅授权到所需对象；
- [ ] 项目、地点、Glossary、数据集、模型的资源路径相互兼容；
- [ ] 已按模型和语言对验证支持矩阵；
- [ ] 已为费用设置 Budget、Alert、配额和 `labels`；
- [ ] 长操作有持久化 operation name、状态跟踪和失败告警；
- [ ] 已以目标语言人工评估术语、格式、保密内容与业务风险；
- [ ] 已明确 Preview 功能（如 RomanizeText）的回退策略。

## 官方文档索引

- [API 概览](https://docs.cloud.google.com/translate/docs/api-overview?hl=zh-cn) · [模型比较](https://docs.cloud.google.com/translate/docs/advanced/compare-models?hl=zh-cn) · [语言](https://docs.cloud.google.com/translate/docs/languages?hl=zh-cn)
- [支持格式](https://docs.cloud.google.com/translate/docs/supported-formats?hl=zh-cn) · [设置](https://docs.cloud.google.com/translate/docs/setup?hl=zh-cn) · [检测语言](https://docs.cloud.google.com/translate/docs/detect-language?hl=zh-cn&usertype=Advanced) · [列出语言](https://docs.cloud.google.com/translate/docs/list-supported-languages?hl=zh-cn&usertype=Advanced)
- [文本翻译](https://docs.cloud.google.com/translate/docs/translate-text?hl=zh-cn) · [批量翻译](https://docs.cloud.google.com/translate/docs/advanced/batch-translation?hl=zh-cn) · [文档翻译](https://docs.cloud.google.com/translate/docs/advanced/translate-documents?hl=zh-cn)
- [Glossary](https://docs.cloud.google.com/translate/docs/advanced/glossary?hl=zh-cn) · [混合术语表教程](https://docs.cloud.google.com/translate/docs/hybrid-glossaries-tutorial?hl=zh-cn) · [罗马化](https://docs.cloud.google.com/translate/docs/advanced/romanize-text?hl=zh-cn) · [无效搜索词](https://docs.cloud.google.com/translate/docs/advanced/stopwords?hl=zh-cn)
- [自适应翻译](https://docs.cloud.google.com/translate/docs/advanced/adaptive-translation?hl=zh-cn) · [自定义翻译](https://docs.cloud.google.com/translate/docs/advanced/custom-translations?hl=zh-cn) · [数据集管理](https://docs.cloud.google.com/translate/docs/advanced/adaptive-translation-data?hl=zh-cn)
