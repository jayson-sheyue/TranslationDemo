const $ = (selector) => document.querySelector(selector);
const TRANSLATION_LLM_MODELS = new Set(["general/translation-llm"]);
const TRANSLATION_LLM_LANGUAGES_URL = "https://cloud.google.com/translate/docs/languages#translation-llm_supported_languages";

function show(target, value) {
  const node = $(target);
  node.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

function formatDetail(detail) {
  if (!detail) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || item.detail || JSON.stringify(item)).join("; ");
  }
  if (typeof detail === "object" && detail.message) return detail.message;
  return JSON.stringify(detail);
}

async function request(path, options = {}) {
  const response = await fetch(path, options);
  const body = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
  if (!response.ok) throw new Error(formatDetail(body.detail) || JSON.stringify(body));
  return body;
}

function jsonFromInput(form, name) {
  const raw = new FormData(form).get(name)?.trim();
  if (!raw) return undefined;
  try { return JSON.parse(raw); } catch { throw new Error(`「${name}」必须是合法 JSON。`); }
}

function payload(form, fields) {
  const data = new FormData(form), out = {};
  for (const field of fields) {
    const value = data.get(field);
    if (value !== null && String(value).trim() !== "") out[field] = String(value).trim();
  }
  return out;
}

function bindJsonForm(selector, url, result, build) {
  $(selector).addEventListener("submit", async (event) => {
    event.preventDefault(); show(result, "请求中…");
    try { show(result, await request(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(build(event.currentTarget)) })); }
    catch (error) { show(result, `错误：${error.message}`); }
  });
}

const GCS_BUCKET_KEY = "gcs-bucket";
let bundledAssets = [];

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}

function bucketName() {
  const first = document.querySelector(".gcs-bucket");
  return (first?.value || localStorage.getItem(GCS_BUCKET_KEY) || "").trim().replace(/^gs:\/\//, "").split("/")[0];
}

function gsUri(objectPath) {
  const bucket = bucketName();
  if (!bucket || !objectPath) return "";
  return `gs://${bucket}/${String(objectPath).replace(/^\/+/, "")}`;
}

function markEdited(event) {
  event.currentTarget.dataset.userEdited = "1";
}

function syncBucketInputs(value) {
  const clean = (value || "").trim().replace(/^gs:\/\//, "").split("/")[0];
  document.querySelectorAll(".gcs-bucket").forEach((el) => { el.value = clean; });
  if (clean) localStorage.setItem(GCS_BUCKET_KEY, clean);
  else localStorage.removeItem(GCS_BUCKET_KEY);
  document.querySelectorAll("[data-gcs-object], [data-fill-gcs]").forEach((el) => {
    if (el.dataset.userEdited) return;
    const objectPath = el.dataset.fillGcs || el.dataset.gcsObject;
    el.value = gsUri(objectPath);
  });
}

function assetById(id) {
  return bundledAssets.find((item) => item.id === id);
}

function renderTable(table) {
  if (!table) return "";
  const head = (table.headers || []).map((cell) => `<th>${escapeHtml(cell)}</th>`).join("");
  const body = (table.rows || []).map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("");
  return `<div class="table-wrap"><table class="asset-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function fillFromAsset(asset, destinationUri) {
  const uri = destinationUri || gsUri(asset.gcs_object);
  if (asset.id === "glossary-product-terms") {
    const form = $("#glossary-form");
    form.glossary_id.value = form.glossary_id.value || "product-terms";
    if (asset.language_codes) form.language_codes.value = asset.language_codes;
    if (uri) form.input_uri.value = uri;
    openPanel("glossary");
    return;
  }
  if (asset.id === "glossary-test-input") {
    const form = $("#translate-form");
    form.contents.value = asset.text.replace(/\s+$/, "");
    form.mime_type.value = "text/plain";
    form.source_language_code.value = "en";
    openPanel("text");
    return;
  }
  if (asset.id === "adaptive-dataset") {
    if (uri) $("#adaptive-file-form").input_uri.value = uri;
    openPanel("adaptive");
    return;
  }
  if (asset.id === "adaptive-test-input") {
    $("#adaptive-form").content.value = asset.text.replace(/\s+$/, "");
    openPanel("adaptive");
    return;
  }
  if (asset.id === "adaptive-ticket" || asset.id === "adaptive-pr") {
    const data = JSON.parse(asset.text);
    const form = $("#adaptive-inline-form");
    form.content.value = data.content;
    form.source_language_code.value = data.source_language_code;
    form.target_language_code.value = data.target_language_code;
    form.reference_pairs.value = JSON.stringify(data.reference_pairs, null, 2);
    openPanel("adaptive");
    return;
  }
  if (asset.id === "text-html") {
    const form = $("#translate-form");
    form.contents.value = asset.text.replace(/\s+$/, "");
    form.mime_type.value = "text/html";
    openPanel("text");
    return;
  }
  if (asset.id === "batch-text") {
    const form = $("#batch-text-form");
    if (uri) form.input_uri.value = uri;
    if (bucketName() && !form.output_uri_prefix.dataset.userEdited) form.output_uri_prefix.value = gsUri("batch/out/");
    openPanel("batch");
  }
}

function renderAssetCard(asset) {
  const preview = asset.table ? renderTable(asset.table) : `<pre class="asset-preview">${escapeHtml(asset.text)}</pre>`;
  const upload = asset.needs_gcs ? `<button type="button" class="secondary" data-asset-upload="${asset.id}">一键上传到我的 GCS</button>` : "";
  return `<article class="asset-card"><div class="asset-card-head"><h3>${escapeHtml(asset.title)}</h3><code>${escapeHtml(asset.path)}</code></div><p class="small">${escapeHtml(asset.note || "")}</p>${preview}<div class="actions"><button type="button" data-asset-fill="${asset.id}">填入表单</button>${upload}</div><pre class="result asset-status" hidden></pre></article>`;
}

function bindAssetLibraries() {
  const groups = [
    { el: $("#glossary-assets"), ids: ["glossary-product-terms", "glossary-test-input"] },
    { el: $("#adaptive-assets"), ids: ["adaptive-dataset", "adaptive-test-input"] },
    { el: $("#batch-assets"), ids: ["batch-text"] },
    { el: $("#text-assets"), ids: ["text-html"] },
  ];
  for (const group of groups) {
    if (!group.el) continue;
    const items = group.ids.map(assetById).filter(Boolean);
    group.el.innerHTML = items.map(renderAssetCard).join("") || `<p class="small">未能加载 assets/ 样例。</p>`;
  }
  document.querySelectorAll("[data-asset-fill]").forEach((button) => {
    button.addEventListener("click", () => {
      const asset = assetById(button.dataset.assetFill);
      if (!asset) return;
      fillFromAsset(asset);
    });
  });
  document.querySelectorAll("[data-asset-upload]").forEach((button) => {
    button.addEventListener("click", async () => {
      const card = button.closest(".asset-card");
      const status = card.querySelector(".asset-status");
      const asset = assetById(button.dataset.assetUpload);
      status.hidden = false;
      status.textContent = "上传中…";
      try {
        if (!bucketName()) throw new Error("请先填写你自己的 GCS 桶名。");
        const result = await request("/api/assets/upload", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ asset_id: asset.id, bucket: bucketName(), object_name: asset.gcs_object }),
        });
        status.textContent = JSON.stringify(result, null, 2);
        fillFromAsset(asset, result.destination_uri);
      } catch (error) {
        status.textContent = `错误：${error.message}`;
      }
    });
  });
}

function bindOwnUpload(formSel, resultSel, onSuccess) {
  const form = $(formSel);
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    show(resultSel, "上传中…");
    try {
      const dest = form.querySelector("[name=destination_uri]");
      if (dest && !dest.value.trim()) dest.value = gsUri(dest.dataset.gcsObject);
      const data = new FormData(form);
      if (bucketName()) data.set("bucket", bucketName());
      const body = await request("/api/assets/upload-file", { method: "POST", body: data });
      show(resultSel, body);
      onSuccess?.(body);
    } catch (error) {
      show(resultSel, `错误：${error.message}`);
    }
  });
}

function openPanel(panelId) {
  document.querySelectorAll(".tab,.panel").forEach((el) => el.classList.remove("active"));
  $(`.tab[data-panel="${panelId}"]`).classList.add("active");
  $(`#${panelId}`).classList.add("active");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => openPanel(tab.dataset.panel)));
document.querySelectorAll("[data-go]").forEach((button) => button.addEventListener("click", () => openPanel(button.dataset.go)));
document.querySelectorAll("[data-scroll]").forEach((button) => button.addEventListener("click", () => {
  const target = $("#" + button.dataset.scroll);
  if (!target) return;
  const panel = target.closest(".panel");
  if (panel && !panel.classList.contains("active") && panel.id) openPanel(panel.id);
  setTimeout(() => target.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
}));

bindJsonForm("#translate-form", "/api/translate", "#translate-result", (form) => {
  const p = payload(form, ["source_language_code", "target_language_code", "mime_type", "model", "custom_model_id", "glossary_id", "location"]);
  if (p.glossary_id && !p.source_language_code) {
    throw new Error("使用术语表时必须填写源语言，例如 en。输入框里浅灰色的示例不会自动提交。");
  }
  p.contents = new FormData(form).get("contents").split("\n").filter(Boolean); p.labels = jsonFromInput(form, "labels"); return p;
});
$("#html-sample").addEventListener("click", () => {
  const asset = assetById("text-html");
  if (asset) { fillFromAsset(asset); return; }
  const form = $("#translate-form");
  form.contents.value = "<h1>Cloud Translation</h1>\n<p>Keep <strong>HTML tags</strong> around the visible words.</p>\n<p>Our product name is Atlas.</p>";
  form.mime_type.value = "text/html";
});
bindJsonForm("#detect-form", "/api/detect", "#detect-result", (form) => payload(form, ["content", "mime_type"]));

function isTranslationLlm(model) {
  return TRANSLATION_LLM_MODELS.has(model);
}

function llmLanguagesMessage() {
  return [
    "Translation LLM 不能使用 GetSupportedLanguages 查询。",
    "该接口只支持 NMT / AutoML；把 general/translation-llm 传进去会得到 501 LLM models are not supported。",
    "这不是鉴权或项目配置错误，也不代表 LLM 不能翻译。",
    "",
    "本 Demo 没有向 Cloud Translation 发起这个请求。",
    "请点击「打开 Translation LLM 官方语言表」，确认源语言和目标语言都在列表中。",
    "然后回到「文本翻译」，用 TranslateText 选择 Translation LLM 即可。",
    "",
    TRANSLATION_LLM_LANGUAGES_URL,
  ].join("\n");
}

function syncLanguagesUi() {
  const form = $("#languages-form");
  const llm = isTranslationLlm(form.model.value);
  const submit = $("#languages-submit");
  submit.disabled = llm;
  submit.textContent = llm ? "此接口不支持 LLM" : "列出支持语言";
  if (llm) {
    show("#languages-result", llmLanguagesMessage());
    return;
  }
  const current = $("#languages-result").textContent;
  if (current.includes("不能使用 GetSupportedLanguages")) {
    show("#languages-result", "选择 NMT 后点击「列出支持语言」，API 会返回该模型支持的语言。");
  }
}

const languagesForm = $("#languages-form");
languagesForm.model.addEventListener("change", syncLanguagesUi);
languagesForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  if (isTranslationLlm(form.model.value)) {
    show("#languages-result", llmLanguagesMessage());
    return;
  }
  show("#languages-result", "请求中…");
  try { show("#languages-result", await request("/api/languages", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload(form, ["display_language_code", "model"])) })); }
  catch (error) { show("#languages-result", `错误：${error.message}`); }
});
syncLanguagesUi();
bindJsonForm("#glossary-form", "/api/glossaries", "#glossary-result", (form) => { const p = payload(form, ["glossary_id", "input_uri", "location"]); p.language_codes = form.language_codes.value.split(",").map((x) => x.trim()).filter(Boolean); return p; });
bindJsonForm("#stopword-form", "/api/glossaries/validate-stopwords", "#stopword-result", (form) => ({ terms: form.terms.value.split(",").map((x) => x.trim()).filter(Boolean) }));
$("#list-glossaries").addEventListener("click", async () => {
  const location = $("#glossary-form").location.value.trim();
  const query = location ? `?location=${encodeURIComponent(location)}` : "";
  show("#glossary-result", "读取中…");
  try { show("#glossary-result", await request(`/api/glossaries${query}`)); }
  catch (e) { show("#glossary-result", `错误：${e.message}`); }
});
bindJsonForm("#batch-text-form", "/api/batch/text", "#batch-text-result", (form) => { const p = payload(form, ["input_uri", "output_uri_prefix", "source_language_code", "mime_type"]); p.target_language_codes = form.target_language_codes.value.split(",").map(x => x.trim()).filter(Boolean); return p; });
bindJsonForm("#batch-document-form", "/api/batch/document", "#batch-document-result", (form) => { const p = payload(form, ["input_uri", "output_uri_prefix", "source_language_code"]); p.target_language_codes = form.target_language_codes.value.split(",").map(x => x.trim()).filter(Boolean); return p; });
bindJsonForm("#dataset-form", "/api/adaptive/datasets", "#adaptive-result", (form) => payload(form, ["dataset_id", "display_name", "source_language_code", "target_language_code"]));
bindJsonForm("#adaptive-form", "/api/adaptive/translate", "#adaptive-result", (form) => payload(form, ["dataset_id", "content"]));
bindJsonForm("#adaptive-inline-form", "/api/adaptive/translate-inline", "#adaptive-result", (form) => ({ ...payload(form, ["content", "source_language_code", "target_language_code"]), reference_pairs: jsonFromInput(form, "reference_pairs") }));
$("#adaptive-file-form").addEventListener("submit", async (event) => { event.preventDefault(); const form = event.currentTarget; show("#adaptive-result", "导入中…"); try { show("#adaptive-result", await request(`/api/adaptive/datasets/${encodeURIComponent(form.dataset_id.value)}/files`, { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({input_uri:form.input_uri.value}) })); } catch (e) { show("#adaptive-result", `错误：${e.message}`); } });
$("#adaptive-files-form").addEventListener("submit", async (event) => { event.preventDefault(); const form = event.currentTarget; show("#adaptive-result", "读取中…"); try { show("#adaptive-result", await request(`/api/adaptive/datasets/${encodeURIComponent(form.dataset_id.value)}/files`)); } catch (e) { show("#adaptive-result", `错误：${e.message}`); } });
$("#list-datasets").addEventListener("click", async () => { show("#adaptive-result", "读取中…"); try { show("#adaptive-result", await request("/api/adaptive/datasets")); } catch (e) { show("#adaptive-result", `错误：${e.message}`); } });
$("#adaptive-inline-sample").addEventListener("click", () => {
  const asset = assetById("adaptive-ticket");
  if (asset) { fillFromAsset(asset); return; }
  const form = $("#adaptive-inline-form");
  form.content.value = "Please open a ticket for this outage.";
  form.source_language_code.value = "en";
  form.target_language_code.value = "zh-CN";
  form.reference_pairs.value = JSON.stringify([
    { source_sentence: "I opened a ticket yesterday.", target_sentence: "我昨天建了一张工单。" },
    { source_sentence: "The ticket is still open.", target_sentence: "这张工单仍未关闭。" },
    { source_sentence: "Close the ticket after the fix.", target_sentence: "修复后请关闭工单。" },
    { source_sentence: "This ticket has high priority.", target_sentence: "此工单优先级很高。" },
    { source_sentence: "Assign the ticket to on-call.", target_sentence: "请把工单派给值班人员。" },
  ], null, 2);
});
$("#adaptive-pr-sample").addEventListener("click", () => {
  const asset = assetById("adaptive-pr");
  if (asset) { fillFromAsset(asset); return; }
  const form = $("#adaptive-inline-form");
  form.content.value = "Please review this PR before lunch.";
  form.source_language_code.value = "en";
  form.target_language_code.value = "zh-CN";
  form.reference_pairs.value = JSON.stringify([
    { source_sentence: "The PR is ready.", target_sentence: "该合并请求已就绪。" },
    { source_sentence: "I merged the PR.", target_sentence: "我已合并该合并请求。" },
    { source_sentence: "Open a PR for the fix.", target_sentence: "请为这次修复开一个合并请求。" },
    { source_sentence: "This PR needs tests.", target_sentence: "这个合并请求还缺测试。" },
    { source_sentence: "Close the PR.", target_sentence: "请关闭该合并请求。" },
  ], null, 2);
});
const adaptiveDatasetInputs = ["#dataset-form", "#adaptive-file-form", "#adaptive-files-form", "#adaptive-form"].map((sel) => $(sel).elements.dataset_id);
adaptiveDatasetInputs.forEach((input) => {
  input.addEventListener("input", () => {
    adaptiveDatasetInputs.forEach((other) => { if (other !== input) other.value = input.value; });
  });
});
bindJsonForm("#romanize-form", "/api/romanize", "#romanize-result", (form) => ({ contents: [form.contents.value], source_language_code: form.source_language_code.value }));

async function sendFile(form, url, result, onSuccess) {
  form.addEventListener("submit", async (event) => { event.preventDefault(); show(result, "上传并请求中…"); try { const response = await request(url, { method: "POST", body: new FormData(form) }); show(result, response); onSuccess?.(response); } catch (error) { show(result, `错误：${error.message}`); } });
}
sendFile($("#document-form"), "/api/document", "#document-result", (data) => { if (!data.files_base64?.length) return; const bytes = atob(data.files_base64[0]), array = new Uint8Array(bytes.length); for (let i=0;i<bytes.length;i++) array[i]=bytes.charCodeAt(i); const url = URL.createObjectURL(new Blob([array], {type:data.mime_type})); const link = document.createElement("a"); link.href=url; link.download=`translated.${data.mime_type.includes("pdf") ? "pdf" : "docx"}`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 60000); });
sendFile($("#image-form"), "/api/image-translate", "#image-result");

request("/api/health").then((data) => { $("#health").textContent = data.project_configured ? `已配置项目：${data.project_id}\n默认区域：${data.default_location}` : `等待配置 GOOGLE_CLOUD_PROJECT\n默认区域：${data.default_location}`; }).catch((error) => { $("#health").textContent = `服务检查失败：${error.message}`; });

document.querySelectorAll(".gcs-bucket").forEach((el) => el.addEventListener("input", () => syncBucketInputs(el.value)));
document.querySelectorAll("[data-gcs-object], [data-fill-gcs]").forEach((el) => el.addEventListener("input", markEdited));
syncBucketInputs(localStorage.getItem(GCS_BUCKET_KEY) || "");
bindOwnUpload("#glossary-own-upload", "#glossary-upload-result", (body) => {
  if (body.destination_uri) $("#glossary-form").input_uri.value = body.destination_uri;
});
bindOwnUpload("#adaptive-own-upload", "#adaptive-upload-result", (body) => {
  if (body.destination_uri) $("#adaptive-file-form").input_uri.value = body.destination_uri;
});
bindOwnUpload("#batch-own-upload", "#batch-upload-result", (body) => {
  if (body.destination_uri) $("#batch-text-form").input_uri.value = body.destination_uri;
});
request("/api/assets").then((data) => {
  bundledAssets = data.assets || [];
  bindAssetLibraries();
}).catch((error) => {
  ["#glossary-assets", "#adaptive-assets", "#batch-assets", "#text-assets"].forEach((sel) => {
    const node = $(sel);
    if (node) node.innerHTML = `<p class="small">未能加载本地样例：${escapeHtml(error.message)}</p>`;
  });
});
