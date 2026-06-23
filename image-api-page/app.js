const els = {
  baseUrl: document.querySelector("#baseUrlInput"),
  apiKey: document.querySelector("#apiKeyInput"),
  model: document.querySelector("#modelInput"),
  refreshQuota: document.querySelector("#refreshQuotaBtn"),
  quotaValue: document.querySelector("#quotaValue"),
  quotaDetail: document.querySelector("#quotaDetail"),
  form: document.querySelector("#imageForm"),
  tabs: Array.from(document.querySelectorAll(".tab")),
  promptLabel: document.querySelector("#promptLabel"),
  prompt: document.querySelector("#promptInput"),
  referenceSection: document.querySelector("#referenceSection"),
  fileInput: document.querySelector("#fileInput"),
  dropZone: document.querySelector("#dropZone"),
  imageUrl: document.querySelector("#imageUrlInput"),
  addUrl: document.querySelector("#addUrlBtn"),
  referenceList: document.querySelector("#referenceList"),
  count: document.querySelector("#countInput"),
  size: document.querySelector("#sizeInput"),
  quality: document.querySelector("#qualityInput"),
  responseFormat: document.querySelector("#responseFormatInput"),
  submit: document.querySelector("#submitBtn"),
  clear: document.querySelector("#clearBtn"),
  status: document.querySelector("#statusText"),
  resultGrid: document.querySelector("#resultGrid"),
  raw: document.querySelector("#rawResponse"),
  copyResponse: document.querySelector("#copyResponseBtn"),
  moreExperience: document.querySelector("#moreExperienceLink"),
  template: document.querySelector("#imageCardTemplate"),
  
  // 新增的 DOM 节点
  toggleConfig: document.querySelector("#toggleConfigBtn"),
  configSection: document.querySelector("#configSection"),
  charCounter: document.querySelector("#charCounter"),
  clearPrompt: document.querySelector("#clearPromptBtn"),
  toastContainer: document.querySelector("#toastContainer"),
};

const settingsKey = "chatgpt2api:image-api-page:settings";
const allowedImageModels = ["codex-gpt-image-2", "gpt-image-2", "plus-codex-gpt-image-2"];
const b64BlobUrlCache = new Map();
let mode = "generate";
let references = [];
let lastResponse = {};

// ==========================================================================
// 辅助函数与 Toast 系统
// ==========================================================================

function createId() {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.append(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}

/**
 * 弹出 Toast 提示通知
 */
function showToast(message, type = "normal", duration = 4000) {
  if (!els.toastContainer) return;
  
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  
  // 匹配图标
  const icon = document.createElement("span");
  icon.className = "toast-icon";
  if (type === "success") {
    icon.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`;
  } else if (type === "error") {
    icon.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/></svg>`;
  } else {
    icon.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="16" y2="12"/><line x1="12" x2="12.01" y1="8" y2="8"/></svg>`;
  }
  
  const text = document.createElement("span");
  text.textContent = message;
  
  const close = document.createElement("button");
  close.className = "toast-close";
  close.innerHTML = "&times;";
  close.type = "button";
  close.addEventListener("click", () => {
    toast.classList.add("fade-out");
    setTimeout(() => toast.remove(), 250);
  });
  
  toast.append(icon, text, close);
  els.toastContainer.appendChild(toast);
  
  setTimeout(() => {
    if (toast.parentNode) {
      toast.classList.add("fade-out");
      setTimeout(() => toast.remove(), 250);
    }
  }, duration);
}

function setStatus(message, type = "normal") {
  els.status.textContent = message;
  
  // 更新导航栏小圆点的状态
  const dot = document.querySelector(".status-dot");
  if (dot) {
    dot.className = "status-dot";
    if (type === "error") {
      dot.classList.add("status-error-dot");
    } else if (type === "ok") {
      dot.classList.add("status-ok-dot");
    }
  }

  // 抛出 Toast 提升视觉感知
  if (type === "error") {
    showToast(message, "error");
  } else if (type === "ok") {
    showToast(message, "success");
  }
}

function setBusy(isBusy) {
  els.form.classList.toggle("busy", isBusy);
  els.submit.disabled = isBusy;
  
  // 更新生图提交按钮状态
  const submitText = els.submit.querySelector("span");
  const submitIcon = els.submit.querySelector("svg");
  
  if (isBusy) {
    if (submitText) submitText.textContent = mode === "edit" ? " 正在编辑..." : " 正在生成...";
    if (submitIcon) {
      submitIcon.innerHTML = `<path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>`;
      submitIcon.classList.add("icon-spin");
    }
  } else {
    if (submitText) submitText.textContent = mode === "edit" ? " 开始编辑" : " 开始生成";
    if (submitIcon) {
      submitIcon.innerHTML = `<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>`;
      submitIcon.classList.remove("icon-spin");
    }
  }
}

function normalizeBaseUrl(value) {
  return String(value || "").trim().replace(/\/+$/, "");
}

function sameOriginBase() {
  return window.location.origin === "null" ? "" : window.location.origin;
}

function apiOriginBase() {
  return sameOriginBase();
}

function apiUrl(path) {
  return `${sameOriginBase()}${path}`;
}

function authHeaders(extra = {}) {
  const key = String(els.apiKey.value || "").trim();
  if (!key) {
    return { ...extra };
  }
  return {
    Authorization: `Bearer ${key}`,
    ...extra,
  };
}

function b64ToBlob(b64, mimeType = "image/png") {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return new Blob([bytes], { type: mimeType });
}

function b64ToBlobUrl(b64) {
  let url = b64BlobUrlCache.get(b64);
  if (!url) {
    url = URL.createObjectURL(b64ToBlob(b64));
    b64BlobUrlCache.set(b64, url);
  }
  return url;
}

function revokeResultBlobUrls() {
  for (const url of b64BlobUrlCache.values()) {
    URL.revokeObjectURL(url);
  }
  b64BlobUrlCache.clear();
}

async function readError(response) {
  const text = await response.text();
  if (!text) {
    return `HTTP ${response.status}`;
  }
  const compact = text.trim().replace(/\s+/g, " ");
  if (/^<!doctype html/i.test(compact) || /^<html/i.test(compact)) {
    if (response.status === 502 || /bad gateway/i.test(compact)) {
      return "图片接口上游暂时不可用（HTTP 502），请稍后重试。";
    }
    return `接口返回了 HTML 错误页（HTTP ${response.status}），请稍后重试。`;
  }
  try {
    const payload = JSON.parse(text);
    const detail = payload.detail || payload.error || payload;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail.error === "string") return detail.error;
    return JSON.stringify(detail);
  } catch {
    return text;
  }
}

async function requestJson(path, options = {}) {
  const url = apiUrl(path);
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  const text = await response.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    const preview = text.trim().replace(/\s+/g, " ").slice(0, 120);
    throw new Error(`接口 ${url} 返回的不是 JSON：${preview || "空响应"}`);
  }
}

function saveSettings() {
  try {
    const data = {
      baseUrl: els.baseUrl.value,
      model: els.model.value,
      size: els.size.value,
      quality: els.quality.value,
      responseFormat: els.responseFormat.value,
      count: els.count.value,
    };
    localStorage.setItem(settingsKey, JSON.stringify(data));
  } catch {
    // Storage can be unavailable in private mode.
  }
}

function syncRatioOptions() {
  const currentVal = els.size ? els.size.value : "";
  const ratioOptions = document.querySelectorAll(".ratio-option");
  ratioOptions.forEach((btn) => {
    const active = btn.dataset.value === currentVal;
    btn.classList.toggle("active", active);
  });
}

function loadSettings() {
  try {
    const data = JSON.parse(localStorage.getItem(settingsKey) || "{}");
    for (const [key, value] of Object.entries(data)) {
      if (key === "apiKey" || key === "baseUrl") {
        continue;
      }
      if (els[key] && typeof value === "string") {
        els[key].value = value;
      }
    }
    delete data.apiKey;
    delete data.baseUrl;
    localStorage.setItem(settingsKey, JSON.stringify(data));
    els.baseUrl.value = "";
    els.apiKey.value = "";
    
    // 如果没有本地保存的 API，则默认展开连接面板，提高引导性
    if (!data.baseUrl && els.configSection) {
      els.configSection.className = "config-panel expanded";
    }
    
    // 同步可视化比例高亮状态
    if (!allowedImageModels.includes(els.model.value)) {
      els.model.value = "gpt-image-2";
    }
    els.responseFormat.value = "b64_json";
    syncRatioOptions();
  } catch {
    // Storage can be unavailable or contain invalid data. Defaults are usable.
  }
}

function resolveMoreExperienceUrl(hostname = window.location.hostname) {
  const host = String(hostname || "").toLowerCase();
  if (host === "image.xiaoleai.team") {
    return "https://xiaoleai.team";
  }
  if (host === "image.aicards.shop") {
    return "https://aicards.shop/";
  }
  return "https://www.xiaoleai.team/";
}

function applyMoreExperienceLink() {
  if (!els.moreExperience) return;
  els.moreExperience.href = resolveMoreExperienceUrl();
}

function setMode(nextMode) {
  mode = nextMode;
  els.tabs.forEach((tab) => {
    const active = tab.dataset.mode === nextMode;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  const isEdit = nextMode === "edit";
  els.referenceSection.classList.toggle("hidden", !isEdit);
  els.promptLabel.textContent = isEdit ? "编辑提示词" : "生图提示词";
  
  const submitText = els.submit.querySelector("span");
  if (submitText) {
    submitText.textContent = isEdit ? " 开始编辑" : " 开始生成";
  }
  els.prompt.placeholder = isEdit
    ? "例如：保持主体构图不变，改成赛博朋克夜景，增加霓虹灯和雨后反光"
    : "例如：一张极简产品海报，白色背景，金属质感耳机，中文标题留白，商业摄影风格";
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error(`读取图片失败：${file.name}`));
    reader.readAsDataURL(file);
  });
}

function b64ToFile(b64, fileName = "generated.png", mimeType = "image/png") {
  return new File([b64ToBlob(b64, mimeType)], fileName, { type: mimeType });
}

async function addFiles(files) {
  const imageFiles = Array.from(files || []).filter((file) => file.type.startsWith("image/") || /\.(png|jpe?g|webp|gif|bmp|svg)$/i.test(file.name));
  for (const file of imageFiles) {
    references.push({
      id: createId(),
      kind: "file",
      name: file.name || "image.png",
      file,
      preview: await fileToDataUrl(file),
    });
  }
  renderReferences();
}

function addImageUrl(url) {
  const value = String(url || "").trim();
  if (!value) return;
  if (!value.startsWith("http://") && !value.startsWith("https://") && !value.startsWith("data:image/")) {
    throw new Error("图片 URL 必须以 http://、https:// 或 data:image/ 开头");
  }
  references.push({
    id: createId(),
    kind: "url",
    name: value.startsWith("data:") ? "data-url-image" : new URL(value).pathname.split("/").pop() || "image-url",
    url: value,
    preview: value,
  });
  els.imageUrl.value = "";
  renderReferences();
}

function renderReferences() {
  els.referenceList.innerHTML = "";
  els.referenceList.classList.toggle("empty", references.length === 0);
  if (references.length === 0) {
    els.referenceList.innerHTML = "<span>暂无参考图</span>";
    return;
  }
  references.forEach((item) => {
    const wrap = document.createElement("div");
    wrap.className = "reference-thumb";
    const img = document.createElement("img");
    img.src = item.preview;
    img.alt = item.name;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.title = "移除参考图";
    remove.textContent = "×";
    remove.addEventListener("click", () => {
      references = references.filter((ref) => ref.id !== item.id);
      renderReferences();
    });
    wrap.append(img, remove);
    els.referenceList.append(wrap);
  });
}

function buildCommonPayload() {
  const prompt = els.prompt.value.trim();
  if (!prompt) {
    throw new Error("请填写提示词");
  }
  const n = Math.min(3, Math.max(1, Number.parseInt(els.count.value || "1", 10) || 1));
  els.count.value = String(n);
  const payload = {
    model: els.model.value.trim() || "gpt-image-2",
    prompt,
    n,
    quality: els.quality.value || "auto",
    response_format: els.responseFormat.value || "b64_json",
  };
  if (els.size.value) {
    payload.size = els.size.value;
  }
  return payload;
}

async function submitGeneration() {
  const payload = buildCommonPayload();
  return requestJson("/v1/images/generations", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
}

async function submitEdit() {
  const payload = buildCommonPayload();
  if (references.length === 0) {
    throw new Error("编辑图至少需要一张参考图");
  }
  const hasFile = references.some((item) => item.kind === "file");
  if (!hasFile) {
    return requestJson("/v1/images/edits", {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        ...payload,
        images: references.map((item) => item.url),
      }),
    });
  }
  const form = new FormData();
  form.append("model", payload.model);
  form.append("prompt", payload.prompt);
  form.append("n", String(payload.n));
  form.append("quality", payload.quality);
  form.append("response_format", payload.response_format);
  if (payload.size) form.append("size", payload.size);
  references.forEach((item) => {
    if (item.kind === "file") {
      form.append("image", item.file, item.name);
    } else {
      form.append("image", item.url);
    }
  });
  return requestJson("/v1/images/edits", {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
}

function imageSrcFromItem(item) {
  if (item.b64_json) {
    return b64ToBlobUrl(item.b64_json);
  }
  if (item.url) {
    return item.url.startsWith("http") ? item.url : new URL(item.url, `${apiOriginBase()}/`).href;
  }
  return "";
}

function shortJson(value) {
  return JSON.stringify(
    value,
    (key, item) => {
      if (typeof item === "string" && item.length > 700) {
        return `${item.slice(0, 700)}... [truncated ${item.length - 700} chars]`;
      }
      return item;
      },
    2,
  );
}

/**
 * 渲染精美的加载骨架屏卡片
 */
function renderSkeletons(count) {
  els.resultGrid.innerHTML = "";
  els.resultGrid.classList.remove("empty");
  for (let i = 0; i < count; i++) {
    const card = document.createElement("div");
    card.className = "skeleton-card";
    card.innerHTML = `
      <div class="skeleton-media"></div>
      <div class="skeleton-info">
        <div class="skeleton-line title"></div>
        <div class="skeleton-line desc"></div>
      </div>
    `;
    els.resultGrid.append(card);
  }
}

function renderResults(payload) {
  revokeResultBlobUrls();
  lastResponse = payload || {};
  els.raw.textContent = shortJson(lastResponse);
  const data = Array.isArray(payload?.data) ? payload.data : [];
  els.resultGrid.innerHTML = "";
  els.resultGrid.classList.toggle("empty", data.length === 0);
  
  if (data.length === 0) {
    els.resultGrid.innerHTML = `
      <div class="empty-state-illustrate">
        <div class="empty-state-icon">
          <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>
        </div>
        <p>接口未返回图片</p>
        <span class="empty-subtext">请展开下方原始 API 响应数据查看报错详情</span>
      </div>
    `;
    return;
  }
  
  let renderedCount = 0;
  data.forEach((item, index) => {
    const src = imageSrcFromItem(item);
    if (!src) return;
    const node = els.template.content.firstElementChild.cloneNode(true);
    const img = node.querySelector("img");
    const preview = node.querySelector(".image-zoom-trigger");
    const title = node.querySelector(".card-number");
    const note = node.querySelector(".card-description");
    const download = node.querySelector(".download-link");
    const useAsRef = node.querySelector(".use-as-ref");
    
    img.src = src;
    title.textContent = `IMAGE #${index + 1}`;
    note.textContent = item.revised_prompt ? `Revised: ${item.revised_prompt}` : item.b64_json ? "format: Base64 PNG" : "format: URL";
    note.title = item.revised_prompt || "";
    
    preview.addEventListener("click", () => window.open(src, "_blank", "noopener,noreferrer"));
    download.href = src;
    download.download = `chatgpt2api-image-${Date.now()}-${index + 1}.png`;
    download.addEventListener("click", (event) => {
      event.preventDefault();
      void downloadImage(item, src, download.download);
    });
    
    useAsRef.addEventListener("click", async () => {
      setMode("edit");
      if (item.b64_json) {
        const file = b64ToFile(item.b64_json, `generated-${index + 1}.png`);
        await addFiles([file]);
      } else if (item.url) {
        addImageUrl(src);
      }
      setStatus("已把结果加入参考图，可继续编辑。", "ok");
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
    
    els.resultGrid.append(node);
    renderedCount += 1;
  });
  
  if (renderedCount === 0) {
    els.resultGrid.classList.add("empty");
    els.resultGrid.innerHTML = `<span>响应中无有效可视化图片。请展开响应数据检查错误。</span>`;
  }
}

async function downloadImage(item, src, filename) {
  try {
    const blob = item.b64_json
      ? b64ToBlob(item.b64_json)
      : await fetch(src).then((response) => {
          if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
          }
          return response.blob();
        });
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(objectUrl);
    showToast("图片已开始下载", "success");
  } catch {
    window.open(src, "_blank", "noopener,noreferrer");
  }
}

function setQuotaDisplay(value, detail = "") {
  if (els.quotaValue) {
    els.quotaValue.textContent = value;
  }
  if (els.quotaDetail) {
    els.quotaDetail.textContent = detail;
  }
}

async function refreshQuota() {
  if (!els.refreshQuota) return;
  els.refreshQuota.disabled = true;
  setQuotaDisplay("...", "获取中");
  try {
    let totalQuota;
    try {
      const health = await requestJson("/health?format=json");
      totalQuota = health?.accounts?.total_quota;
    } catch (error) {
      const payload = await requestJson("/api/accounts/quota", {
        headers: authHeaders(),
      });
      totalQuota = payload.quota;
    }
    totalQuota = Math.max(0, Number.parseInt(totalQuota || 0, 10) || 0);
    const updatedAt = new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
    setQuotaDisplay(String(totalQuota), `${updatedAt} 更新`);
    setStatus(`可用额度已刷新：${totalQuota}`, "ok");
  } catch (error) {
    setQuotaDisplay("--", "无权限或请求失败");
    setStatus(error.message || "获取额度失败", "error");
  } finally {
    els.refreshQuota.disabled = false;
  }
}

async function handleSubmit(event) {
  event.preventDefault();
  saveSettings();
  
  const n = Math.min(3, Math.max(1, Number.parseInt(els.count.value || "1", 10) || 1));
  setBusy(true);
  setStatus(mode === "edit" ? "正在提交图片编辑请求..." : "正在提交图片生成请求...");
  
  // 渲染极具视觉动感的骨架屏卡片
  renderSkeletons(n);
  
  try {
    const startedAt = performance.now();
    const payload = mode === "edit" ? await submitEdit() : await submitGeneration();
    const elapsed = ((performance.now() - startedAt) / 1000).toFixed(1);
    renderResults(payload);
    const count = Array.isArray(payload?.data) ? payload.data.length : 0;
    setStatus(`完成，用时 ${elapsed}s，返回 ${count} 张图片。`, "ok");
  } catch (error) {
    lastResponse = { error: error.message || String(error) };
    els.raw.textContent = shortJson(lastResponse);
    setStatus(error.message || "请求失败", "error");
    
    // 清空骨架屏并复原
    els.resultGrid.innerHTML = `
      <div class="empty-state-illustrate">
        <div class="empty-state-icon">
          <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/></svg>
        </div>
        <p>艺术创作失败</p>
        <span class="empty-subtext">${error.message || "未知接口请求错误"}</span>
      </div>
    `;
    els.resultGrid.classList.add("empty");
  } finally {
    setBusy(false);
  }
}

function bindEvents() {
  // 顶部连接配置折叠
  if (els.toggleConfig && els.configSection) {
    els.toggleConfig.addEventListener("click", () => {
      const isCollapsed = els.configSection.classList.contains("collapsed");
      if (isCollapsed) {
        els.configSection.className = "config-panel expanded";
        els.toggleConfig.classList.add("btn-primary");
      } else {
        els.configSection.className = "config-panel collapsed";
        els.toggleConfig.classList.remove("btn-primary");
      }
    });
  }

  // 提示词输入框相关动效
  if (els.prompt && els.charCounter) {
    const handleInput = () => {
      const length = els.prompt.value.length;
      els.charCounter.textContent = `${length} / 2000`;
      if (els.clearPrompt) {
        els.clearPrompt.style.display = length > 0 ? "flex" : "none";
      }
    };
    els.prompt.addEventListener("input", handleInput);
    
    // 初始化一次
    handleInput();

    if (els.clearPrompt) {
      els.clearPrompt.addEventListener("click", () => {
        els.prompt.value = "";
        handleInput();
        els.prompt.focus();
      });
    }
  }

  els.tabs.forEach((tab) => {
    tab.addEventListener("click", () => setMode(tab.dataset.mode));
  });
  els.form.addEventListener("submit", handleSubmit);
  if (els.refreshQuota) {
    els.refreshQuota.addEventListener("click", refreshQuota);
  }
  els.clear.addEventListener("click", () => {
    revokeResultBlobUrls();
    lastResponse = {};
    els.raw.textContent = "{}";
    els.resultGrid.className = "result-grid-modern empty";
    els.resultGrid.innerHTML = `
      <div class="empty-state-illustrate">
        <div class="empty-state-icon">
          <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>
        </div>
        <p>生成后的艺术图像将呈现在此处</p>
        <span class="empty-subtext">在左侧输入创意提示词并点击生成</span>
      </div>
    `;
    setStatus("已清空结果。");
  });
  els.copyResponse.addEventListener("click", async () => {
    try {
      await copyText(JSON.stringify(lastResponse, null, 2));
      showToast("原始 JSON 响应数据已复制到剪贴板", "success");
    } catch {
      showToast("复制失败，请手动选择数据复制", "error");
    }
  });
  [els.baseUrl, els.apiKey, els.model, els.size, els.quality, els.responseFormat, els.count].forEach((input) => {
    input.addEventListener("change", () => {
      saveSettings();
      if (input === els.size) {
        syncRatioOptions();
      }
    });
  });
  els.count.addEventListener("input", () => {
    const raw = els.count.value.trim();
    if (!raw) return;
    const n = Number.parseInt(raw, 10);
    if (Number.isNaN(n)) {
      els.count.value = "1";
    } else if (n > 3) {
      els.count.value = "3";
    } else if (n < 1) {
      els.count.value = "1";
    }
  });

  // 可视化尺寸选择卡片绑定点击事件
  const ratioOptions = Array.from(document.querySelectorAll(".ratio-option"));
  ratioOptions.forEach((btn) => {
    btn.addEventListener("click", () => {
      const val = btn.dataset.value;
      if (els.size) {
        els.size.value = val;
        els.size.dispatchEvent(new Event("change"));
      }
    });
  });
  els.fileInput.addEventListener("change", async () => {
    try {
      await addFiles(els.fileInput.files);
      els.fileInput.value = "";
    } catch (error) {
      setStatus(error.message || "读取参考图失败", "error");
    }
  });
  els.addUrl.addEventListener("click", () => {
    try {
      addImageUrl(els.imageUrl.value);
    } catch (error) {
      setStatus(error.message, "error");
    }
  });
  els.imageUrl.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      els.addUrl.click();
    }
  });
  ["dragenter", "dragover"].forEach((name) => {
    els.dropZone.addEventListener(name, (event) => {
      event.preventDefault();
      els.dropZone.classList.add("dragging");
    });
  });
  ["dragleave", "drop"].forEach((name) => {
    els.dropZone.addEventListener(name, () => els.dropZone.classList.remove("dragging"));
  });
  els.dropZone.addEventListener("drop", async (event) => {
    event.preventDefault();
    try {
      await addFiles(event.dataTransfer.files);
    } catch (error) {
      setStatus(error.message || "读取参考图失败", "error");
    }
  });
  els.prompt.addEventListener("paste", async (event) => {
    const files = Array.from(event.clipboardData?.files || []).filter((file) => file.type.startsWith("image/"));
    if (!files.length) return;
    event.preventDefault();
    setMode("edit");
    try {
      await addFiles(files);
    } catch (error) {
      setStatus(error.message || "读取参考图失败", "error");
    }
  });
}

// ==========================================================================
// 初始化执行
// ==========================================================================
loadSettings();
applyMoreExperienceLink();
bindEvents();
setMode("generate");
renderReferences();
refreshQuota();
window.addEventListener("beforeunload", revokeResultBlobUrls);

// 在控制台输出精美彩蛋，增添高端专业质感
console.log(
  "%c ChatGPT2API Image Studio %c UI & UX Optimized Successfully! 🚀",
  "background:#6366f1;color:#fff;padding:4px 8px;border-radius:4px 0 0 4px;font-weight:bold;",
  "background:#1e1b4b;color:#a5b4fc;padding:4px 8px;border-radius:0 4px 4px 0;"
);
