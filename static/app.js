const $ = (selector) => document.querySelector(selector);

function show(target, value) {
  const node = $(target);
  node.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

async function request(path, options = {}) {
  const response = await fetch(path, options);
  const body = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
  if (!response.ok) throw new Error(body.detail || JSON.stringify(body));
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

function openPanel(panelId) {
  document.querySelectorAll(".tab,.panel").forEach((el) => el.classList.remove("active"));
  $(`.tab[data-panel="${panelId}"]`).classList.add("active");
  $(`#${panelId}`).classList.add("active");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => openPanel(tab.dataset.panel)));
document.querySelectorAll("[data-go]").forEach((button) => button.addEventListener("click", () => openPanel(button.dataset.go)));
document.querySelectorAll("[data-scroll]").forEach((button) => button.addEventListener("click", () => $("#" + button.dataset.scroll).scrollIntoView({ behavior: "smooth" })));

bindJsonForm("#translate-form", "/api/translate", "#translate-result", (form) => {
  const p = payload(form, ["source_language_code", "target_language_code", "mime_type", "model", "custom_model_id", "glossary_id", "location"]);
  p.contents = new FormData(form).get("contents").split("\n").filter(Boolean); p.labels = jsonFromInput(form, "labels"); return p;
});
$("#html-sample").addEventListener("click", () => { const form = $("#translate-form"); form.contents.value = "<h1>Cloud Translation</h1><p>Keep <strong>HTML tags</strong>.</p>"; form.mime_type.value = "text/html"; });
bindJsonForm("#detect-form", "/api/detect", "#detect-result", (form) => payload(form, ["content", "mime_type"]));
bindJsonForm("#languages-form", "/api/languages", "#languages-result", (form) => payload(form, ["display_language_code", "model"]));
bindJsonForm("#glossary-form", "/api/glossaries", "#glossary-result", (form) => { const p = payload(form, ["glossary_id", "input_uri", "location"]); p.language_codes = form.language_codes.value.split(",").map((x) => x.trim()).filter(Boolean); return p; });
bindJsonForm("#stopword-form", "/api/glossaries/validate-stopwords", "#stopword-result", (form) => ({ terms: form.terms.value.split(",").map((x) => x.trim()).filter(Boolean) }));
$("#list-glossaries").addEventListener("click", async () => { show("#glossary-result", "读取中…"); try { show("#glossary-result", await request("/api/glossaries")); } catch (e) { show("#glossary-result", `错误：${e.message}`); } });
bindJsonForm("#batch-text-form", "/api/batch/text", "#batch-text-result", (form) => { const p = payload(form, ["input_uri", "output_uri_prefix", "source_language_code", "mime_type"]); p.target_language_codes = form.target_language_codes.value.split(",").map(x => x.trim()).filter(Boolean); return p; });
bindJsonForm("#batch-document-form", "/api/batch/document", "#batch-document-result", (form) => { const p = payload(form, ["input_uri", "output_uri_prefix", "source_language_code"]); p.target_language_codes = form.target_language_codes.value.split(",").map(x => x.trim()).filter(Boolean); return p; });
bindJsonForm("#dataset-form", "/api/adaptive/datasets", "#adaptive-result", (form) => payload(form, ["dataset_id", "display_name", "source_language_code", "target_language_code"]));
bindJsonForm("#adaptive-form", "/api/adaptive/translate", "#adaptive-result", (form) => payload(form, ["dataset_id", "content"]));
bindJsonForm("#adaptive-inline-form", "/api/adaptive/translate-inline", "#adaptive-result", (form) => ({ ...payload(form, ["content", "source_language_code", "target_language_code"]), reference_pairs: jsonFromInput(form, "reference_pairs") }));
$("#adaptive-file-form").addEventListener("submit", async (event) => { event.preventDefault(); const form = event.currentTarget; show("#adaptive-result", "导入中…"); try { show("#adaptive-result", await request(`/api/adaptive/datasets/${encodeURIComponent(form.dataset_id.value)}/files`, { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({input_uri:form.input_uri.value}) })); } catch (e) { show("#adaptive-result", `错误：${e.message}`); } });
$("#adaptive-files-form").addEventListener("submit", async (event) => { event.preventDefault(); const form = event.currentTarget; show("#adaptive-result", "读取中…"); try { show("#adaptive-result", await request(`/api/adaptive/datasets/${encodeURIComponent(form.dataset_id.value)}/files`)); } catch (e) { show("#adaptive-result", `错误：${e.message}`); } });
$("#list-datasets").addEventListener("click", async () => { show("#adaptive-result", "读取中…"); try { show("#adaptive-result", await request("/api/adaptive/datasets")); } catch (e) { show("#adaptive-result", `错误：${e.message}`); } });
bindJsonForm("#romanize-form", "/api/romanize", "#romanize-result", (form) => ({ contents: [form.contents.value], source_language_code: form.source_language_code.value }));

async function sendFile(form, url, result, onSuccess) {
  form.addEventListener("submit", async (event) => { event.preventDefault(); show(result, "上传并请求中…"); try { const response = await request(url, { method: "POST", body: new FormData(form) }); show(result, response); onSuccess?.(response); } catch (error) { show(result, `错误：${error.message}`); } });
}
sendFile($("#document-form"), "/api/document", "#document-result", (data) => { if (!data.files_base64?.length) return; const bytes = atob(data.files_base64[0]), array = new Uint8Array(bytes.length); for (let i=0;i<bytes.length;i++) array[i]=bytes.charCodeAt(i); const url = URL.createObjectURL(new Blob([array], {type:data.mime_type})); const link = document.createElement("a"); link.href=url; link.download=`translated.${data.mime_type.includes("pdf") ? "pdf" : "docx"}`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 60000); });
sendFile($("#image-form"), "/api/image-translate", "#image-result");

request("/api/health").then((data) => { $("#health").textContent = data.project_configured ? `已配置项目：${data.project_id}\n默认区域：${data.default_location}` : `等待配置 GOOGLE_CLOUD_PROJECT\n默认区域：${data.default_location}`; }).catch((error) => { $("#health").textContent = `服务检查失败：${error.message}`; });
