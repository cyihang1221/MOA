const modelSelect = document.getElementById("modelSelect");
const tempInput = document.getElementById("tempInput");
const messagesEl = document.getElementById("messages");
const form = document.getElementById("chatForm");
const promptInput = document.getElementById("promptInput");
const sendButton = document.getElementById("sendButton");
const stopButton = document.getElementById("stopButton");
const newSessionBtn = document.getElementById("newSessionBtn");
const clearSessionBtn = document.getElementById("clearSessionBtn");
const sessionListEl = document.getElementById("sessionList");
const statusText = document.getElementById("statusText");
const fileInput = document.getElementById("fileInput");
const attachBtn = document.getElementById("attachBtn");
const attachmentBar = document.getElementById("attachmentBar");
const attachmentList = document.getElementById("attachmentList");
const composer = document.getElementById("composer");
const shareBtn = document.getElementById("shareBtn");
const shareStatus = document.getElementById("shareStatus");
const sharedBanner = document.getElementById("sharedBanner");
const exitShareViewBtn = document.getElementById("exitShareViewBtn");
const welcomePanel = document.getElementById("welcomePanel");
const toolsPanel = document.getElementById("toolsPanel");
const toolsSidebar = document.getElementById("toolsSidebar");
const toolsCount = document.getElementById("toolsCount");
const runtimeInfo = document.getElementById("runtimeInfo");
const filesPanel = document.getElementById("filesPanel");
const refreshFilesBtn = document.getElementById("refreshFilesBtn");
const inputFilesList = document.getElementById("inputFilesList");
const outputFilesList = document.getElementById("outputFilesList");
const inputFilesDir = document.getElementById("inputFilesDir");
const outputFilesDir = document.getElementById("outputFilesDir");
const filesPanelHint = document.getElementById("filesPanelHint");
const outputImageGallery = document.getElementById("outputImageGallery");
const imageLightbox = document.getElementById("imageLightbox");
const lightboxBackdrop = document.getElementById("lightboxBackdrop");
const lightboxImg = document.getElementById("lightboxImg");
const lightboxTitle = document.getElementById("lightboxTitle");
const lightboxClose = document.getElementById("lightboxClose");
const imageEditor = document.getElementById("imageEditor");
const editorBackdrop = document.getElementById("editorBackdrop");
const editorClose = document.getElementById("editorClose");
const editorTitle = document.getElementById("editorTitle");
const editorStage = document.getElementById("editorStage");
const editorTextInput = document.getElementById("editorTextInput");
const editorColorInput = document.getElementById("editorColorInput");
const editorFontSizeInput = document.getElementById("editorFontSizeInput");
const editorTitlePosition = document.getElementById("editorTitlePosition");
const editorStageScaler = document.getElementById("editorStageScaler");
const editorAddTitle = document.getElementById("editorAddTitle");
const editorAddText = document.getElementById("editorAddText");
const editorAddArrow = document.getElementById("editorAddArrow");
const editorAddColorBlock = document.getElementById("editorAddColorBlock");
const editorDelete = document.getElementById("editorDelete");
const editorSave = document.getElementById("editorSave");
const editorCancel = document.getElementById("editorCancel");
const editorStatus = document.getElementById("editorStatus");
const plotlyEditor = document.getElementById("plotlyEditor");
const plotlyEditorBackdrop = document.getElementById("plotlyEditorBackdrop");
const plotlyEditorClose = document.getElementById("plotlyEditorClose");
const plotlyEditorTitle = document.getElementById("plotlyEditorTitle");
const plotlyEditorHint = document.getElementById("plotlyEditorHint");
const plotlyChart = document.getElementById("plotlyChart");
const plotlyLegendColorInput = document.getElementById("plotlyLegendColorInput");
const plotlyLegendColorRow = document.getElementById("plotlyLegendColorRow");
const plotlyTraceSelect = document.getElementById("plotlyTraceSelect");
const plotlyEditorSave = document.getElementById("plotlyEditorSave");
const plotlyEditorCancel = document.getElementById("plotlyEditorCancel");
const plotlyEditorStatus = document.getElementById("plotlyEditorStatus");

const IMAGE_EXT_RE = /\.(png|jpe?g|gif|webp|svg)$/i;

const t = (key, params) => window.MassI18n.t(key, params);

function normalizePath(path) {
  if (!path) return "";
  return String(path).replace(/\\/g, "/");
}

function isImagePath(path) {
  return IMAGE_EXT_RE.test(normalizePath(path));
}

function toWorkspaceRel(path) {
  const norm = normalizePath(path);
  const match = norm.match(/(?:outputspace|inputspace)\/[^/]+\/(.+)$/i);
  return match ? match[1] : null;
}

function workspaceFileUrl(sessionId, relOrAbs) {
  if (!sessionId) return null;
  const rel = relOrAbs.includes("/") && !relOrAbs.startsWith("outputspace")
    ? toWorkspaceRel(relOrAbs) || relOrAbs.replace(/^\/+/, "")
    : relOrAbs;
  if (!rel || rel.includes("..")) return null;
  return `/api/sessions/${sessionId}/workspace-file?rel=${encodeURIComponent(rel)}`;
}

let sessions = [];
let currentSessionId = null;
let isSharedView = false;
let pendingFiles = [];
let isStreaming = false;
let activeStreamAbort = null;
let lastAssistantMessageId = null;
let appRuntime = null;
let imageEditorState = {
  stage: null,
  layer: null,
  transformer: null,
  selectedNode: null,
  displayScale: 1,
  sourceRel: "",
  sourceTitle: "",
  editMeta: null,
  imageNode: null,
  rasterCanvas: null,
  rasterCtx: null,
  pickedRasterColor: null,
};
let plotlyEditorState = {
  sourceRel: "",
  sourceTitle: "",
  selectedTrace: null,
};

function getUrlParams() {
  return new URLSearchParams(window.location.search);
}

function buildShareUrl(sessionId) {
  const url = new URL(window.location.href);
  url.search = "";
  url.searchParams.set("session", sessionId);
  url.searchParams.set("view", "shared");
  return url.toString();
}

function updateBrowserUrl(sessionId, shared = false) {
  const url = new URL(window.location.href);
  if (sessionId && shared) {
    url.searchParams.set("session", sessionId);
    url.searchParams.set("view", "shared");
  } else if (sessionId) {
    url.searchParams.set("session", sessionId);
    url.searchParams.delete("view");
  } else {
    url.search = "";
  }
  window.history.replaceState({}, "", url.toString());
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function nowString() {
  const now = new Date();
  return `${now.getHours().toString().padStart(2, "0")}:${now
    .getMinutes()
    .toString()
    .padStart(2, "0")}`;
}

function displayTime(t) {
  if (!t) return "";
  const m = String(t).match(/T(\d\d:\d\d)/);
  if (m && m[1]) return m[1];
  return String(t);
}

function setStatus(text) {
  statusText.textContent = text || "";
}

function setSharedViewMode(enabled) {
  isSharedView = enabled;
  sharedBanner.classList.toggle("hidden", !enabled);
  composer.classList.toggle("hidden", enabled);
  newSessionBtn.disabled = enabled;
  clearSessionBtn.disabled = enabled;
  shareBtn.disabled = enabled;
  attachBtn.disabled = enabled;
  filesPanel.classList.toggle("hidden", enabled);
}

function createDownloadLink(sessionId, rel, label) {
  const url = workspaceFileUrl(sessionId, rel);
  if (!url) return null;
  const link = document.createElement("a");
  link.className = "file-download-link";
  link.href = url;
  link.download = String(rel).split("/").pop() || "download";
  link.textContent = label || t("files.download");
  link.title = t("files.download");
  link.addEventListener("click", (event) => event.stopPropagation());
  return link;
}

function renderFileTree(listEl, files, emptyMsg, { sessionId = null, excludeImages = false } = {}) {
  listEl.innerHTML = "";
  const list = (files || []).filter((file) => !excludeImages || !isImagePath(file.name));
  if (!list.length) {
    const li = document.createElement("li");
    li.className = "file-empty";
    li.textContent = emptyMsg;
    listEl.appendChild(li);
    return;
  }
  list.forEach((file) => {
    const li = document.createElement("li");
    li.className = "file-item";
    li.title = file.path || "";

    const main = document.createElement("div");
    main.className = "file-item-main";
    const name = document.createElement("span");
    name.className = "file-name";
    name.textContent = file.name;
    const meta = document.createElement("span");
    meta.className = "file-meta";
    meta.textContent = formatSize(file.size || 0);
    main.appendChild(name);
    main.appendChild(meta);
    li.appendChild(main);

    if (sessionId && !isSharedView) {
      const download = createDownloadLink(sessionId, file.name);
      if (download) li.appendChild(download);
    }
    listEl.appendChild(li);
  });
}

function renderOutputImageGallery(files, sessionId) {
  if (!outputImageGallery) return;
  outputImageGallery.innerHTML = "";
  const images = (files || []).filter((file) => isImagePath(file.name));
  outputImageGallery.classList.toggle("hidden", images.length === 0);
  if (!images.length || !sessionId || isSharedView) return;

  images.forEach((file) => {
    const url = workspaceFileUrl(sessionId, file.name);
    if (!url) return;

    const item = document.createElement("article");
    item.className = "output-image-item";

    const thumbBtn = document.createElement("button");
    thumbBtn.type = "button";
    thumbBtn.className = "output-image-thumb";
    const img = document.createElement("img");
    img.loading = "lazy";
    img.alt = file.name;
    img.src = url;
    thumbBtn.appendChild(img);
    thumbBtn.addEventListener("click", () => {
      openImageLightbox({ url, title: file.name.split("/").pop() });
    });

    const side = document.createElement("div");
    side.className = "output-image-side";
    const title = document.createElement("div");
    title.className = "output-image-name";
    title.textContent = file.name.split("/").pop();
    title.title = file.name;
    const meta = document.createElement("div");
    meta.className = "output-image-meta";
    meta.textContent = formatSize(file.size || 0);
    const download = createDownloadLink(sessionId, file.name, t("image.download"));
    if (download) download.classList.add("output-image-download");
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "output-image-edit secondary-btn small-btn";
    editBtn.textContent = t("image.edit");
    editBtn.addEventListener("click", async (event) => {
      event.stopPropagation();
      await openImageEditor({
        url,
        rel: file.name,
        title: file.name.split("/").pop(),
      });
    });

    side.appendChild(title);
    side.appendChild(meta);
    side.appendChild(editBtn);
    if (download) side.appendChild(download);

    item.appendChild(thumbBtn);
    item.appendChild(side);
    outputImageGallery.appendChild(item);
  });
}

async function loadWorkspaceFiles(sessionId) {
  if (!sessionId || isSharedView) {
    renderFileTree(inputFilesList, [], t("files.empty"));
    renderFileTree(outputFilesList, [], t("files.empty"));
    renderOutputImageGallery([], sessionId);
    inputFilesDir.textContent = "";
    outputFilesDir.textContent = "";
    return;
  }
  try {
    const res = await fetch(`/api/sessions/${sessionId}/workspace-files`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || t("files.loadFail", { msg: "" }));
    filesPanelHint.textContent = data.storage_slug
      ? t("files.slug", { slug: data.storage_slug })
      : t("files.current");
    inputFilesDir.textContent = data.inputs_dir || "";
    outputFilesDir.textContent = data.outputs_dir || "";
    renderOutputImageGallery(data.outputs || [], sessionId);
    renderFileTree(inputFilesList, data.inputs, t("files.noInput"), { sessionId });
    renderFileTree(outputFilesList, data.outputs, t("files.noOutput"), {
      sessionId,
      excludeImages: true,
    });
  } catch (err) {
    filesPanelHint.textContent = t("files.loadFail", { msg: err.message });
  }
}

function renderAttachments() {
  attachmentList.innerHTML = "";
  attachmentBar.classList.toggle("hidden", pendingFiles.length === 0);
  pendingFiles.forEach((file, index) => {
    const chip = document.createElement("div");
    chip.className = "attachment-chip";
    chip.innerHTML = `
      <span class="attachment-name" title="${file.name}">${file.name}</span>
      <span class="attachment-size">${formatSize(file.size)}</span>
      <button type="button" aria-label="${t("attach.remove")}">×</button>
    `;
    chip.querySelector("button").addEventListener("click", () => {
      pendingFiles.splice(index, 1);
      renderAttachments();
    });
    attachmentList.appendChild(chip);
  });
}

function addPendingFiles(fileList) {
  const existing = new Set(pendingFiles.map((f) => `${f.name}:${f.size}`));
  Array.from(fileList || []).forEach((file) => {
    const key = `${file.name}:${file.size}`;
    if (!existing.has(key)) {
      pendingFiles.push(file);
      existing.add(key);
    }
  });
  renderAttachments();
}

function setStreamingState(streaming) {
  isStreaming = streaming;
  sendButton.classList.toggle("hidden", streaming);
  stopButton.classList.toggle("hidden", !streaming);
  sendButton.disabled = streaming;
  attachBtn.disabled = streaming || isSharedView;
  promptInput.disabled = streaming || isSharedView;
}

function forceStopStreamingUI() {
  setStreamingState(false);
  activeStreamAbort = null;
}

function applyCompletionStatus(payload) {
  if (payload?.cancelled) {
    statusText.className = "status-text status-warn";
    setStatus(t("status.cancelled"));
    return;
  }
  if (payload?.error) {
    statusText.className = "status-text status-error";
    setStatus(t("status.error", { msg: payload.error }));
    return;
  }
  if (payload?.finished !== false) {
    statusText.className = "status-text status-ok";
    setStatus(t("status.done"));
    return;
  }
  statusText.className = "status-text";
  setStatus(t("status.complete"));
}

function createMessageEl(role, content, timeStr = "", messageId = null) {
  const div = document.createElement("div");
  div.className = `message ${role}`;
  if (messageId != null) div.dataset.messageId = String(messageId);

  const contentEl = document.createElement("div");
  contentEl.className = "message-content";
  contentEl.textContent = content || "";

  const actionsEl = document.createElement("div");
  actionsEl.className = "message-actions";
  // 仅用户提问可编辑；助手回答不可修改
  if (!isSharedView && messageId != null && role === "user") {
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "message-action-btn";
    editBtn.textContent = t("msg.edit");
    editBtn.addEventListener("click", () =>
      openMessageEditor(div, messageId, getMessagePlainText(contentEl))
    );
    actionsEl.appendChild(editBtn);
  }

  const metaEl = document.createElement("div");
  metaEl.className = "message-meta";
  const label = role === "user" ? t("role.user") : t("role.assistant");
  metaEl.textContent = `${label} · ${displayTime(timeStr) || ""}`;

  div.appendChild(contentEl);
  if (actionsEl.childElementCount) div.appendChild(actionsEl);
  div.appendChild(metaEl);
  messagesEl.appendChild(div);
  scrollMessagesIfPinned(true);

  if (role === "assistant" && messageId != null) {
    lastAssistantMessageId = messageId;
  }
  return { div, contentEl, metaEl, actionsEl };
}

function getMessagePlainText(contentEl) {
  return contentEl?.textContent || "";
}

function openMessageEditor(messageDiv, messageId, currentText) {
  if (isStreaming) {
    setStatus(t("status.waitEdit"));
    return;
  }
  const contentEl = messageDiv.querySelector(".message-content");
  const existing = messageDiv.querySelector(".message-editor-wrap");
  if (existing) return;

  const wrap = document.createElement("div");
  wrap.className = "message-editor-wrap";
  const editor = document.createElement("textarea");
  editor.className = "message-editor";
  editor.value = currentText || getMessagePlainText(contentEl);

  const btnRow = document.createElement("div");
  btnRow.className = "message-edit-actions";
  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "secondary-btn small-btn";
  cancelBtn.textContent = t("msg.cancel");
  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  saveBtn.className = "small-btn";
  saveBtn.textContent = t("msg.saveResend");

  const closeEditor = () => {
    wrap.remove();
    contentEl.classList.remove("hidden");
  };

  cancelBtn.addEventListener("click", closeEditor);
  saveBtn.addEventListener("click", async () => {
    const newText = editor.value.trim();
    if (!newText) return;
    closeEditor();
    try {
      await resendFromEditedUser(messageId, newText);
    } catch (err) {
      setStatus(t("status.failed", { msg: err.message }));
    }
  });

  btnRow.appendChild(cancelBtn);
  btnRow.appendChild(saveBtn);
  wrap.appendChild(editor);
  wrap.appendChild(btnRow);
  contentEl.classList.add("hidden");
  messageDiv.insertBefore(wrap, messageDiv.querySelector(".message-meta"));
}

async function resendFromEditedUser(messageId, content) {
  const userEl = messagesEl.querySelector(`[data-message-id="${messageId}"]`);
  const contentEl = userEl?.querySelector(".message-content");
  if (contentEl) contentEl.textContent = content;
  const idx = Array.from(messagesEl.querySelectorAll(".message")).findIndex(
    (el) => el.dataset.messageId === String(messageId)
  );
  if (idx >= 0) {
    const toRemove = [];
    Array.from(messagesEl.querySelectorAll(".message")).forEach((el, i) => {
      if (i > idx) toRemove.push(el);
    });
    toRemove.forEach((el) => el.remove());
  }
  await runAssistantStream({
    userMessage: content,
    editMessageId: messageId,
    useAgent: shouldUseAgent(content),
  });
}

function renderToolsCatalog(categories, targetEl, compact = false) {
  targetEl.innerHTML = "";
  const catLabel = window.MassI18n.toolCategoryLabel;
  const descLabel = window.MassI18n.toolDescriptionLabel;
  categories.forEach((group) => {
    const section = document.createElement("section");
    section.className = compact ? "tools-group compact" : "tools-group";
    const title = document.createElement("h3");
    const catId = group.category_id || group.category;
    title.textContent = catLabel(catId);
    section.appendChild(title);

    const list = document.createElement("div");
    list.className = "tools-grid";
    group.tools.forEach((tool) => {
      const card = document.createElement("article");
      card.className = "tool-card";
      card.innerHTML = `
        <div class="tool-name">${tool.name}</div>
        <div class="tool-desc">${descLabel(tool.name, tool.description)}</div>
      `;
      list.appendChild(card);
    });
    section.appendChild(list);
    targetEl.appendChild(section);
  });
}

function openImageLightbox({ url, title }) {
  if (!url || !imageLightbox) return;
  lightboxImg.src = url;
  lightboxImg.alt = title || "";
  lightboxTitle.textContent = title || "";
  imageLightbox.classList.remove("hidden");
  imageLightbox.setAttribute("aria-hidden", "false");
}

function closeImageLightbox() {
  if (!imageLightbox) return;
  imageLightbox.classList.add("hidden");
  imageLightbox.setAttribute("aria-hidden", "true");
  lightboxImg.removeAttribute("src");
}

function setEditorStatus(text, kind = "") {
  if (!editorStatus) return;
  editorStatus.textContent = text || "";
  editorStatus.className = kind ? `image-editor-status ${kind}` : "image-editor-status";
}

function resetImageEditor() {
  if (imageEditorState.stage) {
    imageEditorState.stage.destroy();
  }
  imageEditorState = {
    stage: null,
    layer: null,
    transformer: null,
    selectedNode: null,
    displayScale: 1,
    sourceRel: "",
    sourceTitle: "",
    editMeta: null,
    imageNode: null,
    rasterCanvas: null,
    rasterCtx: null,
    pickedRasterColor: null,
  };
  if (editorStage) editorStage.innerHTML = "";
  if (editorStageScaler) {
    editorStageScaler.style.width = "";
    editorStageScaler.style.height = "";
  }
  if (editorTextInput) editorTextInput.value = "";
  if (editorTitlePosition) editorTitlePosition.value = "top-center";
  setEditorStatus("");
}

function plotlyCompanionRel(imageRel) {
  return String(imageRel || "").replace(/\.(png|jpe?g|gif|webp|svg)$/i, ".plotly.json");
}

function editableCompanionRel(imageRel) {
  return String(imageRel || "").replace(/\.(png|jpe?g|gif|webp|svg)$/i, ".editable.json");
}

async function fetchEditableMeta(rel) {
  if (!currentSessionId || !rel) return null;
  const url = workspaceFileUrl(currentSessionId, editableCompanionRel(rel));
  if (!url) return null;
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

async function fetchPlotlyFigure(rel) {
  if (!currentSessionId || !rel) return null;
  const url = workspaceFileUrl(currentSessionId, plotlyCompanionRel(rel));
  if (!url) return null;
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const figure = await res.json();
    if (!figure || typeof figure !== "object") return null;
    return figure;
  } catch {
    return null;
  }
}

function fitKonvaStageDisplay(natW, natH) {
  const maxWidth = Math.min(1100, Math.max(360, window.innerWidth - 300));
  const maxHeight = Math.min(760, Math.max(280, window.innerHeight - 180));
  const scale = Math.min(1, maxWidth / natW, maxHeight / natH);
  const displayW = Math.max(1, Math.ceil(natW * scale));
  const displayH = Math.max(1, Math.ceil(natH * scale));
  if (editorStageScaler) {
    editorStageScaler.style.width = `${displayW}px`;
    editorStageScaler.style.height = `${displayH}px`;
  }
  if (editorStage) {
    editorStage.style.width = `${natW}px`;
    editorStage.style.height = `${natH}px`;
    editorStage.style.transform = `scale(${scale})`;
    editorStage.style.transformOrigin = "top left";
  }
  imageEditorState.displayScale = scale;
  return scale;
}

function editableFileStem(name) {
  return String(name || "image").replace(/\.[^.]+$/, "");
}

function setSelectedEditorNode(node) {
  const state = imageEditorState;
  state.selectedNode = node || null;
  if (state.transformer) {
    state.transformer.nodes(node ? [node] : []);
    state.transformer.moveToTop();
    state.transformer.keepRatio(false);
    state.transformer.enabledAnchors(
      node && node.getClassName && node.getClassName() === "Rect"
        ? [
            "top-left",
            "top-center",
            "top-right",
            "middle-left",
            "middle-right",
            "bottom-left",
            "bottom-center",
            "bottom-right",
          ]
        : ["top-left", "top-right", "bottom-left", "bottom-right"]
    );
  }
  if (editorDelete) editorDelete.disabled = !node;
  if (editorTextInput) {
    editorTextInput.disabled = !node || typeof node.text !== "function";
    editorTextInput.value = node && typeof node.text === "function" ? node.text() : "";
  }
  if (editorColorInput && node) {
    const color = typeof node.fill === "function" ? node.fill() : node.stroke?.();
    if (/^#[0-9a-f]{6}$/i.test(color || "")) editorColorInput.value = color;
  }
  if (editorFontSizeInput && node && typeof node.fontSize === "function") {
    editorFontSizeInput.value = String(node.fontSize());
  }
  if (editorTitlePosition && node?.name?.() === "editable-title") {
    editorTitlePosition.value = node.getAttr("titlePosition") || "top-center";
  }
  state.layer?.batchDraw();
}

function bindEditableNode(node) {
  node.on("click tap", (event) => {
    event.cancelBubble = true;
    setSelectedEditorNode(node);
  });
  node.on("dragstart", () => setSelectedEditorNode(node));
  return node;
}

function rgbToHex(r, g, b) {
  return `#${[r, g, b].map((v) => Math.max(0, Math.min(255, v)).toString(16).padStart(2, "0")).join("")}`;
}

function hexToRgb(hex) {
  const m = String(hex || "").match(/^#?([0-9a-f]{6})$/i);
  if (!m) return null;
  const n = Number.parseInt(m[1], 16);
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}

function colorDistance(a, b) {
  return Math.sqrt((a.r - b.r) ** 2 + (a.g - b.g) ** 2 + (a.b - b.b) ** 2);
}

function prepareRasterCanvas(img, width, height) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(img, 0, 0, width, height);
  imageEditorState.rasterCanvas = canvas;
  imageEditorState.rasterCtx = ctx;
  return canvas;
}

function pickRasterColorAt(x, y) {
  const { rasterCtx, rasterCanvas } = imageEditorState;
  if (!rasterCtx || !rasterCanvas) return null;
  const px = Math.max(0, Math.min(rasterCanvas.width - 1, Math.floor(x)));
  const py = Math.max(0, Math.min(rasterCanvas.height - 1, Math.floor(y)));
  const [r, g, b, a] = rasterCtx.getImageData(px, py, 1, 1).data;
  if (a < 10) return null;
  const color = { r, g, b };
  imageEditorState.pickedRasterColor = color;
  setSelectedEditorNode(null);
  if (editorColorInput) editorColorInput.value = rgbToHex(r, g, b);
  setEditorStatus(t("image.rasterColorPicked", { color: rgbToHex(r, g, b) }));
  return color;
}

function replaceRasterColor(targetColor, replacementHex, tolerance = 55) {
  const replacement = hexToRgb(replacementHex);
  const { rasterCtx, rasterCanvas, imageNode } = imageEditorState;
  if (!targetColor || !replacement || !rasterCtx || !rasterCanvas || !imageNode) return;

  const imageData = rasterCtx.getImageData(0, 0, rasterCanvas.width, rasterCanvas.height);
  const data = imageData.data;
  let changed = 0;
  for (let i = 0; i < data.length; i += 4) {
    if (data[i + 3] < 10) continue;
    const current = { r: data[i], g: data[i + 1], b: data[i + 2] };
    const dist = colorDistance(current, targetColor);
    if (dist > tolerance) continue;
    const weight = Math.max(0.25, 1 - dist / tolerance);
    data[i] = Math.round(current.r * (1 - weight) + replacement.r * weight);
    data[i + 1] = Math.round(current.g * (1 - weight) + replacement.g * weight);
    data[i + 2] = Math.round(current.b * (1 - weight) + replacement.b * weight);
    changed += 1;
  }
  rasterCtx.putImageData(imageData, 0, 0);
  imageNode.image(rasterCanvas);
  imageEditorState.layer?.batchDraw();
  imageEditorState.pickedRasterColor = replacement;
  setEditorStatus(t("image.rasterColorApplied", { count: changed }));
}

function titlePositionCoords(position, stage) {
  const width = stage?.width() || 800;
  const height = stage?.height() || 600;
  const textWidth = Math.min(Math.max(width * 0.45, 260), Math.max(280, width - 80));
  const y = position === "inside" ? Math.max(32, height * 0.08) : 24;
  if (position === "top-left") return { x: 36, y, width: textWidth, align: "left" };
  if (position === "top-right") {
    return { x: Math.max(36, width - textWidth - 36), y, width: textWidth, align: "right" };
  }
  return { x: Math.max(36, (width - textWidth) / 2), y, width: textWidth, align: "center" };
}

function applyTitlePosition(position, node = imageEditorState.selectedNode) {
  const state = imageEditorState;
  if (!state.stage || !node || node.getClassName?.() !== "Text") return;
  node.setAttrs(titlePositionCoords(position, state.stage));
  node.setAttr("titlePosition", position);
  state.layer?.batchDraw();
}

function addEditorText(text, options = {}) {
  const state = imageEditorState;
  if (!state.layer) return null;
  const width = state.stage?.width() || 800;
  const isTitle = options.role === "title";
  const titleAttrs = isTitle
    ? titlePositionCoords(options.titlePosition || editorTitlePosition?.value || "top-center", state.stage)
    : {};
  const node = new Konva.Text({
    x: options.x ?? titleAttrs.x ?? Math.max(24, width * 0.08),
    y: options.y ?? titleAttrs.y ?? 24,
    width: options.width ?? titleAttrs.width,
    align: options.align ?? titleAttrs.align,
    text,
    fontSize: Number(editorFontSizeInput?.value || options.fontSize || 28),
    fontFamily: "Arial",
    fontStyle: options.fontStyle || "normal",
    fill: options.fill || editorColorInput?.value || "#111827",
    rotation: options.rotation || 0,
    draggable: true,
    padding: 4,
    name: isTitle ? "editable-title" : "editable-text",
    titlePosition: options.titlePosition || (isTitle ? editorTitlePosition?.value || "top-center" : undefined),
  });
  state.layer.add(bindEditableNode(node));
  setSelectedEditorNode(node);
  return node;
}

function addEditorArrow() {
  const state = imageEditorState;
  if (!state.layer || !state.stage) return null;
  const width = state.stage.width();
  const height = state.stage.height();
  const node = new Konva.Arrow({
    points: [
      Math.max(40, width * 0.25),
      Math.max(60, height * 0.35),
      Math.max(160, width * 0.55),
      Math.max(100, height * 0.35),
    ],
    pointerLength: 14,
    pointerWidth: 14,
    fill: editorColorInput?.value || "#ef4444",
    stroke: editorColorInput?.value || "#ef4444",
    strokeWidth: 4,
    draggable: true,
    name: "editable-arrow",
  });
  state.layer.add(bindEditableNode(node));
  setSelectedEditorNode(node);
  return node;
}

function addEditorColorBlock() {
  const state = imageEditorState;
  if (!state.layer || !state.stage) return null;
  const node = new Konva.Rect({
    x: Math.max(24, state.stage.width() * 0.08),
    y: Math.max(80, state.stage.height() * 0.18),
    width: 28,
    height: 18,
    fill: editorColorInput?.value || "#2563eb",
    stroke: "#ffffff",
    strokeWidth: 1,
    draggable: true,
    name: "editable-rect",
  });
  state.layer.add(bindEditableNode(node));
  setSelectedEditorNode(node);
  return node;
}

function restoreEditableObject(obj) {
  if (!obj || !imageEditorState.layer) return;
  if (obj.type === "text" || obj.type === "title") {
    addEditorText(obj.text || "", {
      role: obj.type === "title" ? "title" : "text",
      x: obj.x,
      y: obj.y,
      width: obj.width,
      align: obj.align,
      fontSize: obj.fontSize,
      fontStyle: obj.fontStyle,
      fill: obj.fill,
      rotation: obj.rotation,
      titlePosition: obj.titlePosition,
    });
    return;
  }
  if (obj.type === "arrow") {
    const node = addEditorArrow();
    node?.setAttrs({
      x: obj.x || 0,
      y: obj.y || 0,
      points: obj.points || node.points(),
      fill: obj.fill || node.fill(),
      stroke: obj.stroke || node.stroke(),
      strokeWidth: obj.strokeWidth || node.strokeWidth(),
      rotation: obj.rotation || 0,
    });
    return;
  }
  if (obj.type === "rect") {
    const node = addEditorColorBlock();
    node?.setAttrs({
      x: obj.x ?? node.x(),
      y: obj.y ?? node.y(),
      width: obj.width || node.width(),
      height: obj.height || node.height(),
      fill: obj.fill || node.fill(),
      stroke: obj.stroke || node.stroke(),
      strokeWidth: obj.strokeWidth ?? node.strokeWidth(),
      rotation: obj.rotation || 0,
    });
  }
}

function serializeEditableState() {
  const state = imageEditorState;
  const objects = [];
  state.layer?.children?.forEach((node) => {
    if (!node.name || !String(node.name()).startsWith("editable-")) return;
    const klass = node.getClassName?.();
    if (klass === "Text") {
      const isTitle = node.name() === "editable-title";
      objects.push({
        type: isTitle ? "title" : "text",
        text: node.text(),
        x: node.x(),
        y: node.y(),
        width: node.width(),
        align: node.align?.(),
        fontSize: node.fontSize(),
        fontStyle: node.fontStyle(),
        fill: node.fill(),
        rotation: node.rotation(),
        titlePosition: node.getAttr("titlePosition"),
      });
    } else if (klass === "Arrow") {
      objects.push({
        type: "arrow",
        x: node.x(),
        y: node.y(),
        points: node.points(),
        fill: node.fill(),
        stroke: node.stroke(),
        strokeWidth: node.strokeWidth(),
        rotation: node.rotation(),
      });
    } else if (klass === "Rect") {
      objects.push({
        type: "rect",
        x: node.x(),
        y: node.y(),
        width: node.width(),
        height: node.height(),
        fill: node.fill(),
        stroke: node.stroke(),
        strokeWidth: node.strokeWidth(),
        rotation: node.rotation(),
      });
    }
  });
  return {
    version: 1,
    source_rel: state.sourceRel,
    title: state.editMeta?.title || editableFileStem(state.sourceTitle),
    title_position: editorTitlePosition?.value || "top-center",
    width: state.stage?.width(),
    height: state.stage?.height(),
    objects,
  };
}

function openKonvaEditor({ url, rel, title, editMeta = null }) {
  if (!url || !rel || !imageEditor || !editorStage) return;
  if (!window.Konva) {
    setStatus(t("image.editorUnavailable"));
    return;
  }
  closeImageLightbox();
  closePlotlyEditor();
  resetImageEditor();
  imageEditorState.sourceRel = rel;
  imageEditorState.sourceTitle = title || rel.split("/").pop();
  imageEditorState.editMeta = editMeta;
  editorTitle.textContent = t("image.editorTitle", { name: imageEditorState.sourceTitle });
  imageEditor.classList.remove("hidden");
  imageEditor.setAttribute("aria-hidden", "false");
  setEditorStatus(t("image.loading"));

  const img = new Image();
  img.onload = () => {
    const natW = Math.max(1, img.naturalWidth);
    const natH = Math.max(1, img.naturalHeight);
    fitKonvaStageDisplay(natW, natH);
    const stage = new Konva.Stage({
      container: editorStage,
      width: natW,
      height: natH,
    });
    const layer = new Konva.Layer();
    const rasterCanvas = prepareRasterCanvas(img, natW, natH);
    const imageNode = new Konva.Image({
      x: 0,
      y: 0,
      width: natW,
      height: natH,
      image: rasterCanvas,
      listening: true,
    });
    imageNode.on("click tap", (event) => {
      event.cancelBubble = true;
      const pos = stage.getPointerPosition();
      if (pos) pickRasterColorAt(pos.x, pos.y);
    });
    const transformer = new Konva.Transformer({
      rotateEnabled: true,
      enabledAnchors: ["top-left", "top-right", "bottom-left", "bottom-right"],
      keepRatio: false,
      boundBoxFunc: (oldBox, newBox) => {
        if (newBox.width < 6 || newBox.height < 6) return oldBox;
        return newBox;
      },
    });

    layer.add(imageNode);
    layer.add(transformer);
    stage.add(layer);
    stage.on("click tap", (event) => {
      if (event.target === stage) setSelectedEditorNode(null);
    });
    imageEditorState.stage = stage;
    imageEditorState.layer = layer;
    imageEditorState.transformer = transformer;
    imageEditorState.imageNode = imageNode;
    if (editorTitlePosition && editMeta?.title_position) {
      editorTitlePosition.value = editMeta.title_position;
    }
    (editMeta?.objects || []).forEach(restoreEditableObject);
    if (!editMeta?.objects?.length && editMeta?.title) {
      addEditorText(editMeta.title, {
        role: "title",
        fontStyle: "bold",
        titlePosition: editMeta.title_position || "top-center",
      });
    } else {
      setSelectedEditorNode(null);
    }
    setEditorStatus(t("image.ready"));
  };
  img.onerror = () => setEditorStatus(t("image.loadFail"), "error");
  img.src = `${url}${url.includes("?") ? "&" : "?"}edit=${Date.now()}`;
}

async function openImageEditor({ url, rel, title }) {
  const plotlyFigure = await fetchPlotlyFigure(rel);
  if (plotlyFigure) {
    openPlotlyEditor({ rel, title, figure: plotlyFigure });
    return;
  }
  const editMeta = await fetchEditableMeta(rel);
  openKonvaEditor({ url, rel, title, editMeta });
}

function setPlotlyEditorStatus(text, kind = "") {
  if (!plotlyEditorStatus) return;
  plotlyEditorStatus.textContent = text || "";
  plotlyEditorStatus.className = kind ? `plotly-editor-status ${kind}` : "plotly-editor-status";
}

function traceColorValue(trace) {
  if (!trace) return "#111827";
  const markerColor = trace.marker?.color;
  if (typeof markerColor === "string") return markerColor;
  if (Array.isArray(markerColor) && markerColor.length) return markerColor[0];
  if (typeof trace.line?.color === "string") return trace.line.color;
  if (typeof trace.fillcolor === "string") return trace.fillcolor;
  return "#111827";
}

function applyPlotlyTraceColor(traceIndex, color) {
  if (!plotlyChart || !window.Plotly || traceIndex == null) return;
  const trace = plotlyChart.data?.[traceIndex];
  if (!trace) return;
  const update = {};
  if (trace.type === "scatter" && trace.mode && String(trace.mode).includes("lines")) {
    update["line.color"] = color;
    if (trace.marker) update["marker.color"] = color;
  } else if (trace.type === "bar" || trace.type === "histogram") {
    update["marker.color"] = color;
  } else {
    update["marker.color"] = color;
    if (trace.line) update["line.color"] = color;
  }
  Plotly.restyle(plotlyChart, update, [traceIndex]);
  setPlotlyEditorStatus(t("image.plotlyColorApplied", { name: trace.name || traceIndex + 1 }));
}

function plotlyTraceLabel(trace, index) {
  return trace?.name || `Series ${index + 1}`;
}

function selectPlotlyTrace(traceIndex, { openPicker = false } = {}) {
  if (!plotlyChart || traceIndex == null || traceIndex < 0) return;
  const trace = plotlyChart.data?.[traceIndex];
  if (!trace) return;

  plotlyEditorState.selectedTrace = traceIndex;
  const label = plotlyTraceLabel(trace, traceIndex);

  if (plotlyLegendColorRow) plotlyLegendColorRow.classList.remove("hidden");
  if (plotlyTraceSelect && plotlyTraceSelect.value !== String(traceIndex)) {
    plotlyTraceSelect.value = String(traceIndex);
  }
  if (plotlyLegendColorInput) {
    plotlyLegendColorInput.value = traceColorValue(trace);
    plotlyLegendColorInput.disabled = false;
    if (openPicker) {
      requestAnimationFrame(() => {
        try {
          if (typeof plotlyLegendColorInput.showPicker === "function") {
            plotlyLegendColorInput.showPicker();
          }
        } catch {
          /* 浏览器可能禁止自动弹出；用户可点击色块 */
        }
      });
    }
  }
  setPlotlyEditorStatus(t("image.plotlyPickLegend", { name: label }));
}

function populatePlotlyTraceSelect(traces) {
  if (!plotlyTraceSelect) return;
  plotlyTraceSelect.innerHTML = "";
  const items = (traces || []).map((trace, index) => ({ trace, index })).filter(
    ({ trace }) => trace.showlegend !== false
  );
  if (!items.length) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = t("image.plotlyNoLegend");
    plotlyTraceSelect.appendChild(opt);
    plotlyTraceSelect.disabled = true;
    return;
  }
  plotlyTraceSelect.disabled = false;
  items.forEach(({ trace, index }) => {
    const opt = document.createElement("option");
    opt.value = String(index);
    opt.textContent = plotlyTraceLabel(trace, index);
    plotlyTraceSelect.appendChild(opt);
  });
  plotlyTraceSelect.value = String(items[0].index);
}

function bindPlotlyLegendColorPicker() {
  if (!plotlyChart || !window.Plotly) return;
  if (typeof plotlyChart.removeAllListeners === "function") {
    plotlyChart.removeAllListeners("plotly_legendclick");
    plotlyChart.removeAllListeners("plotly_legenddoubleclick");
  }
  plotlyChart.on("plotly_legendclick", (event) => {
    selectPlotlyTrace(event.curveNumber, { openPicker: true });
    return false;
  });
  plotlyChart.on("plotly_legenddoubleclick", () => false);
}

function plotlyTitleText(layout) {
  const title = layout?.title;
  if (typeof title === "string") return title;
  if (title && typeof title.text === "string") return title.text;
  return "";
}

function normalizePlotlyLayoutForEditing(layout = {}) {
  const next = JSON.parse(JSON.stringify(layout || {}));
  const titleText = plotlyTitleText(next);
  const annotations = Array.isArray(next.annotations) ? next.annotations : [];
  const hasEditableTitle = annotations.some((item) => item?.name === "editable-title");

  if (titleText && !hasEditableTitle) {
    annotations.push({
      name: "editable-title",
      text: titleText,
      x: next.title?.x ?? 0.5,
      y: next.title?.y ?? 1.08,
      xref: "paper",
      yref: "paper",
      xanchor: next.title?.xanchor || "center",
      yanchor: next.title?.yanchor || "bottom",
      showarrow: false,
      font: next.title?.font || { size: 18, color: "#111827" },
    });
    next.title = { ...(typeof next.title === "object" ? next.title : {}), text: "" };
  }

  next.annotations = annotations;
  next.legend = {
    x: 1.02,
    y: 1,
    ...(next.legend || {}),
  };
  return next;
}

function openPlotlyEditor({ rel, title, figure }) {
  if (!plotlyEditor || !plotlyChart || !window.Plotly) {
    openKonvaEditor({
      url: workspaceFileUrl(currentSessionId, rel),
      rel,
      title,
    });
    return;
  }
  closeImageLightbox();
  closeImageEditor();
  plotlyEditorState.sourceRel = rel;
  plotlyEditorState.sourceTitle = title || rel.split("/").pop();
  plotlyEditorState.selectedTrace = null;
  if (plotlyLegendColorInput) {
    plotlyLegendColorInput.value = "#111827";
    plotlyLegendColorInput.disabled = true;
  }
  populatePlotlyTraceSelect(figure.data || []);
  plotlyEditorTitle.textContent = t("image.plotlyEditorTitle", {
    name: plotlyEditorState.sourceTitle,
  });
  if (plotlyEditorHint) plotlyEditorHint.textContent = t("image.plotlyHint");
  plotlyEditor.classList.remove("hidden");
  plotlyEditor.setAttribute("aria-hidden", "false");
  setPlotlyEditorStatus(t("image.loading"));

  const layout = {
    ...normalizePlotlyLayoutForEditing(figure.layout || {}),
    autosize: true,
    margin: figure.layout?.margin || { l: 60, r: 30, t: 80, b: 60 },
  };
  Plotly.react(plotlyChart, figure.data || [], layout, {
    responsive: true,
    editable: true,
    edits: {
      annotationPosition: true,
      annotationText: true,
      legendPosition: true,
      legendText: true,
      titleText: true,
      axisTitleText: true,
    },
    displayModeBar: false,
  }).then(() => {
    bindPlotlyLegendColorPicker();
    if (plotlyTraceSelect?.value) {
      selectPlotlyTrace(Number(plotlyTraceSelect.value), { openPicker: false });
    }
    setPlotlyEditorStatus(t("image.plotlyReady"));
  });
}

function closePlotlyEditor() {
  if (!plotlyEditor) return;
  plotlyEditor.classList.add("hidden");
  plotlyEditor.setAttribute("aria-hidden", "true");
  if (plotlyChart && window.Plotly) {
    Plotly.purge(plotlyChart);
    plotlyChart.innerHTML = "";
  }
  plotlyEditorState = { sourceRel: "", sourceTitle: "", selectedTrace: null };
  setPlotlyEditorStatus("");
}

async function savePlotlyEdit() {
  if (!currentSessionId || !plotlyChart || !window.Plotly || !plotlyEditorState.sourceRel) return;
  try {
    setPlotlyEditorStatus(t("image.saving"));
    if (plotlyEditorSave) plotlyEditorSave.disabled = true;
    const width = Math.max(900, plotlyChart.offsetWidth || 1100);
    const height = Math.max(540, plotlyChart.offsetHeight || 640);
    const imageData = await Plotly.toImage(plotlyChart, {
      format: "png",
      width,
      height,
      scale: 2,
    });
    const figureJson = {
      data: JSON.parse(JSON.stringify(plotlyChart.data || [])),
      layout: JSON.parse(JSON.stringify(plotlyChart.layout || {})),
    };
    const stem = editableFileStem(plotlyEditorState.sourceTitle);
    const res = await fetch(`/api/sessions/${currentSessionId}/plotly-edits`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_rel: plotlyEditorState.sourceRel,
        figure_json: figureJson,
        image_data: imageData,
        filename: `${stem}_edited.png`,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || t("image.saveFail"));
    closePlotlyEditor();
    await loadWorkspaceFiles(currentSessionId);
    setStatus(t("image.saved", { name: data.file?.name || `${stem}_edited.png` }));
  } catch (err) {
    setPlotlyEditorStatus(t("image.saveFailWithMsg", { msg: err.message }), "error");
  } finally {
    if (plotlyEditorSave) plotlyEditorSave.disabled = false;
  }
}

function closeImageEditor() {
  if (!imageEditor) return;
  imageEditor.classList.add("hidden");
  imageEditor.setAttribute("aria-hidden", "true");
  resetImageEditor();
}

async function saveImageEdit() {
  const state = imageEditorState;
  if (!currentSessionId || !state.stage || !state.sourceRel) return;
  try {
    setEditorStatus(t("image.saving"));
    if (editorSave) editorSave.disabled = true;
    setSelectedEditorNode(null);
    const stem = editableFileStem(state.sourceTitle);
    const imageData = state.stage.toDataURL({ mimeType: "image/png", pixelRatio: 1 });
    const res = await fetch(`/api/sessions/${currentSessionId}/image-edits`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_rel: state.sourceRel,
        image_data: imageData,
        edit_state: serializeEditableState(),
        filename: `${stem}_edited.png`,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || t("image.saveFail"));
    closeImageEditor();
    await loadWorkspaceFiles(currentSessionId);
    setStatus(t("image.saved", { name: data.file?.name || `${stem}_edited.png` }));
  } catch (err) {
    setEditorStatus(t("image.saveFailWithMsg", { msg: err.message }), "error");
  } finally {
    if (editorSave) editorSave.disabled = false;
  }
}

function isMessagesNearBottom(threshold = 96) {
  return (
    messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight <= threshold
  );
}

function scrollMessagesIfPinned(force = false) {
  if (force || isMessagesNearBottom()) {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }
}

function renderRuntimeInfo(runtime) {
  if (!runtimeInfo) return;
  if (!runtime) {
    runtimeInfo.textContent = t("runtime.unavailable");
    return;
  }
  appRuntime = runtime;
  const sep = window.MassI18n.getLang() === "en" ? ": " : "：";
  const lines = [];
  lines.push(`${t("runtime.platform")}${sep}${runtime.platform || t("runtime.unknown")}`);
  if (runtime.preferred_raw_converter?.tool) {
    lines.push(`${t("runtime.rawConv")}${sep}${runtime.preferred_raw_converter.tool}`);
  }
  lines.push(
    `${t("runtime.r")}${sep}${runtime.r_available ? t("runtime.available") : t("runtime.notDetected")}`
  );
  lines.push(
    `${t("runtime.docker")}${sep}${runtime.docker_available ? t("runtime.available") : t("runtime.notDetected")}`
  );

  runtimeInfo.innerHTML = "";
  const list = document.createElement("ul");
  list.className = "runtime-list";
  lines.forEach((text) => {
    const li = document.createElement("li");
    li.textContent = text;
    list.appendChild(li);
  });
  runtimeInfo.appendChild(list);

  if (runtime.issues?.length) {
    const warn = document.createElement("p");
    warn.className = "runtime-warn";
    warn.textContent = runtime.issues.join("；");
    runtimeInfo.appendChild(warn);
  } else if (runtime.agent_ready) {
    runtimeInfo.classList.remove("muted");
    runtimeInfo.classList.add("runtime-ok");
  }
}

function fetchTimeoutSignal(ms) {
  if (typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function") {
    return AbortSignal.timeout(ms);
  }
  const ctrl = new AbortController();
  setTimeout(() => ctrl.abort(), ms);
  return ctrl.signal;
}

async function initRuntime() {
  if (!runtimeInfo) return;
  try {
    const res = await fetch("/api/info", { signal: fetchTimeoutSignal(8000) });
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    renderRuntimeInfo(data.runtime || null);
  } catch {
    runtimeInfo.textContent = t("runtime.detectFailed");
  }
}

async function initTools() {
  // 暂时隐藏左侧可用工具栏，跳过 /api/tools 请求
  return;
  try {
    const res = await fetch("/api/tools", { signal: fetchTimeoutSignal(60000) });
    const data = await res.json();
    // if (toolsCount) toolsCount.textContent = data.total ? `(${data.total})` : "";
    if (toolsPanel) {
      renderToolsCatalog(data.categories || [], toolsPanel, false);
    }
    // if (toolsSidebar) {
    //   renderToolsCatalog(data.categories || [], toolsSidebar, true);
    // }
  } catch {
    if (toolsPanel) {
      toolsPanel.innerHTML = `<p class='muted'>${t("tools.loadFail")}</p>`;
    }
  }
}

async function initModels() {
  try {
    const res = await fetch("/api/models");
    const data = await res.json();
    const models = data.models || [];
    if (models.length === 0 && data.default_model) models.push(data.default_model);
    modelSelect.innerHTML = "";
    models.forEach((model) => {
      const option = document.createElement("option");
      option.value = model;
      option.textContent = model;
      if (data.default_model && model === data.default_model) option.selected = true;
      modelSelect.appendChild(option);
    });
  } catch {
    modelSelect.innerHTML = `<option value=''>${t("models.loadFail")}</option>`;
  }
}

async function fetchSessions() {
  const res = await fetch("/api/sessions");
  if (!res.ok) throw new Error(t("err.fetchSessions"));
  const data = await res.json();
  sessions = data.sessions || [];
}

async function createSession({ title, model, temperature } = {}) {
  const body = {
    model: model || null,
    temperature: Number(temperature || 0),
  };
  if (title) body.title = title;
  const res = await fetch("/api/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || t("err.createSession"));
  return data.session_id;
}

async function deleteSession(sessionId) {
  const res = await fetch(`/api/sessions/${sessionId}`, { method: "DELETE" });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || t("err.deleteSession"));
}

async function renameSession(sessionId, title) {
  const res = await fetch(`/api/sessions/${sessionId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || t("err.renameSession"));
}

async function enableShare(sessionId) {
  const res = await fetch(`/api/sessions/${sessionId}/share`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ shared: true }),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || t("err.enableShare"));
}

async function uploadSingleFile(sessionId, file) {
  const formData = new FormData();
  const name = file.name || "upload.bin";
  formData.append("files", file, name);
  const res = await fetch(`/api/sessions/${sessionId}/files`, {
    method: "POST",
    body: formData,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail || t("err.upload");
    throw new Error(`${name}: ${detail}`);
  }
  return data.files || [];
}

async function uploadPendingFiles(sessionId) {
  if (pendingFiles.length === 0) return [];
  const queue = pendingFiles.filter((file) => file && file.size > 0);
  if (!queue.length) {
    pendingFiles = [];
    renderAttachments();
    throw new Error(t("err.uploadEmpty"));
  }

  const saved = [];
  for (let i = 0; i < queue.length; i += 1) {
    const file = queue[i];
    setStatus(t("status.uploadingProgress", { current: i + 1, total: queue.length, name: file.name }));
    const batch = await uploadSingleFile(sessionId, file);
    saved.push(...batch);
  }
  pendingFiles = [];
  renderAttachments();
  return saved;
}

/** 与 web_frontend/backend/agent_intent.py 语义一致 */
function shouldUseAgent(message, hasNewUpload = false) {
  if (hasNewUpload) return true;
  const text = (message || "").trim();
  if (!text) return false;
  if (/\[已上传附件\]|\[Attachments uploaded\]/.test(text)) return true;
  return /继续|重新(?:运行|进行|分析|做)|执行分析|跑一遍|开始分析|运行工具|分子网(?:络|格)|molecular\s*network|GNPS|DeepMASS|deepmass|XCMS|峰检测|差异代谢|谱库注释|富集分析|converted_mzml|spectra\.mgf|\.mzML|\.mgf|continue|re-?run|run analysis|start agent|execute pipeline/i.test(
    text
  );
}

function buildUserMessage(text, uploadedFiles) {
  const trimmed = (text || "").trim();
  if (!uploadedFiles.length) return trimmed;

  const fileLines = uploadedFiles
    .map(
      (f) =>
        `- ${f.name} (${formatSize(f.size)})\n  ${t("upload.path")}: ${normalizePath(f.path)}`
    )
    .join("\n");

  const base = trimmed || t("upload.defaultPrompt");
  const marker = t("upload.marker");

  return `${base}\n\n${marker}\n${fileLines}\n\n${t("upload.suffix")}`;
}

function renderSessionList() {
  sessionListEl.innerHTML = "";
  if (isSharedView) {
    const item = document.createElement("div");
    item.className = "session-item active";
    item.textContent = t("session.shared");
    sessionListEl.appendChild(item);
    return;
  }

  sessions.forEach((session) => {
    const item = document.createElement("div");
    item.className = `session-item ${session.id === currentSessionId ? "active" : ""}`;
    const titleEl = document.createElement("div");
    titleEl.className = "session-title";
    titleEl.textContent = session.title || t("session.unnamed");
    if (session.is_shared) {
      const badge = document.createElement("span");
      badge.className = "share-badge";
      badge.textContent = t("session.sharedBadge");
      titleEl.appendChild(badge);
    }
    const actionsEl = document.createElement("div");
    actionsEl.className = "session-actions";
    const renameBtn = document.createElement("button");
    renameBtn.type = "button";
    renameBtn.className = "session-action-btn";
    renameBtn.textContent = t("session.rename");
    renameBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const newTitle = prompt(
        t("session.renamePrompt"),
        session.title || t("session.newTitle")
      );
      if (!newTitle) return;
      await renameSession(session.id, newTitle.trim());
      await fetchSessions();
      currentSessionId = session.id;
      renderSessionList();
      await loadSessionView(currentSessionId);
    });
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "session-action-btn";
    deleteBtn.textContent = t("session.delete");
    deleteBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      if (
        !confirm(
          t("session.deleteConfirm", { title: session.title || t("session.unnamed") })
        )
      )
        return;
      await deleteSession(session.id);
      await bootSessionsAndLoad();
    });
    item.appendChild(titleEl);
    actionsEl.appendChild(renameBtn);
    actionsEl.appendChild(deleteBtn);
    item.appendChild(actionsEl);
    item.addEventListener("click", async () => {
      currentSessionId = session.id;
      updateBrowserUrl(session.id, false);
      renderSessionList();
      await loadSessionView(currentSessionId);
    });
    sessionListEl.appendChild(item);
  });
}

function toggleWelcomePanel(show) {
  if (!welcomePanel) return;
  welcomePanel.classList.toggle("hidden", !show);
}

async function loadMessages(sessionId) {
  messagesEl.innerHTML = "";
  const res = await fetch(`/api/sessions/${sessionId}/messages`);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || t("err.loadMessages"));
  const msgs = data.messages || [];
  toggleWelcomePanel(msgs.length <= 1);
  lastAssistantMessageId = null;
  msgs.forEach((m) => createMessageEl(m.role, m.content, m.time || "", m.id));
}

async function loadSessionView(sessionId) {
  await loadMessages(sessionId);
  await loadWorkspaceFiles(sessionId);
}

async function loadSharedMessages(sessionId) {
  messagesEl.innerHTML = "";
  const res = await fetch(`/api/public/sessions/${sessionId}/messages`);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || t("err.sharedNotFound"));
  toggleWelcomePanel(false);
  (data.messages || []).forEach((m) => createMessageEl(m.role, m.content, m.time || "", m.id));
}

async function bootSessionsAndLoad() {
  await fetchSessions();
  if (!sessions.length) {
    currentSessionId = await createSession({
      model: modelSelect.value || null,
      temperature: Number(tempInput.value || 0),
    });
    await fetchSessions();
  }
  if (!sessions.find((s) => s.id === currentSessionId) && sessions.length) {
    currentSessionId = sessions[0].id;
  }
  renderSessionList();
  await loadSessionView(currentSessionId);
  updateBrowserUrl(currentSessionId, false);
}

async function enterSharedView(sessionId) {
  setSharedViewMode(true);
  currentSessionId = sessionId;
  await loadSharedMessages(sessionId);
  renderSessionList();
  updateBrowserUrl(sessionId, true);
}

async function consumeSseStream(res, onDelta, onDone, onError, signal) {
  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  while (true) {
    if (signal?.aborted) {
      try {
        await reader.cancel();
      } catch {
        /* ignore */
      }
      throw new DOMException("Aborted", "AbortError");
    }
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      for (const line of part.split("\n")) {
        if (!line.startsWith("data:")) continue;
        const dataStr = line.slice(5).trim();
        if (!dataStr) continue;
        let payload;
        try {
          payload = JSON.parse(dataStr);
        } catch {
          continue;
        }
        if (payload?.delta !== undefined) onDelta(payload.delta);
        else if (payload?.done) onDone(payload);
        else if (payload?.error) onError(payload.error);
      }
    }
  }
}

async function streamChat({
  sessionId,
  userMessage,
  model,
  temperature,
  useAgent,
  editMessageId,
  signal,
  onDelta,
  onDone,
  onError,
}) {
  let res;
  try {
    res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal,
      body: JSON.stringify({
        session_id: sessionId,
        user_message: userMessage,
        model: model || null,
        temperature: Number(temperature || 0),
        use_agent: Boolean(useAgent),
        edit_message_id:
          editMessageId != null ? Number(editMessageId) : null,
        regenerate_assistant: false,
      }),
    });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new Error(t("err.network"));
  }
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(detail || t("err.requestFailed", { status: res.status }));
  }
  try {
    await consumeSseStream(res, onDelta, onDone, onError, signal);
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new Error(t("err.streamInterrupted"));
  }
}

async function runAssistantStream({
  userMessage,
  useAgent = false,
  editMessageId = null,
}) {
  if (!currentSessionId) return;
  setStreamingState(true);
  activeStreamAbort = new AbortController();

  const assistantEl = createMessageEl("assistant", "", "");
  let assistantText = "";
  setStatus(
    useAgent
      ? t("status.agentMode", {
          platform: appRuntime?.platform || t("status.crossPlatform"),
        })
      : t("status.replying")
  );

  try {
    await streamChat({
      sessionId: currentSessionId,
      userMessage,
      model: modelSelect.value || null,
      temperature: Number(tempInput.value || 0),
      useAgent,
      editMessageId,
      signal: activeStreamAbort.signal,
      onDelta: (delta) => {
        assistantText += delta;
        assistantEl.contentEl.textContent = assistantText;
        scrollMessagesIfPinned();
      },
      onDone: (payload) => {
        if (payload?.time) {
          assistantEl.metaEl.textContent = `${t("role.assistant")} · ${displayTime(payload.time)}`;
        }
        if (payload?.error) {
          assistantEl.contentEl.textContent = assistantText || payload.error;
        }
        if (payload?.finished && !payload?.cancelled) {
          const tail = "\n\n---\n✅ **分析已完成**";
          if (!assistantText.includes("分析已完成")) {
            assistantText += tail;
            assistantEl.contentEl.textContent = assistantText;
          }
        }
        scrollMessagesIfPinned();
        applyCompletionStatus(payload);
      },
      onError: (msg) => {
        assistantEl.contentEl.textContent = msg;
      },
    });
    await fetchSessions();
    renderSessionList();
    await loadSessionView(currentSessionId);
  } catch (err) {
    if (err.name === "AbortError") {
      const partial = (assistantEl.contentEl.textContent || "").trim();
      assistantEl.contentEl.textContent = partial
        ? `${partial}\n\n⚠️ **[已终止]**`
        : "⚠️ **[已终止]**";
      statusText.className = "status-text status-warn";
      setStatus(t("status.cancelledBg"));
      try {
        await loadSessionView(currentSessionId);
      } catch {
        /* ignore */
      }
    } else {
      statusText.className = "status-text status-error";
      setStatus(t("status.failed", { msg: err.message }));
    }
  } finally {
    forceStopStreamingUI();
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (isSharedView) return;
  if (isStreaming) {
    setStatus(t("status.streaming"));
    return;
  }

  const text = promptInput.value.trim();
  if (!text && pendingFiles.length === 0) return;
  if (!currentSessionId) await bootSessionsAndLoad();

  try {
    setStatus(pendingFiles.length ? t("status.uploading") : t("status.sending"));
    const uploaded = await uploadPendingFiles(currentSessionId);
    if (uploaded.length) await loadWorkspaceFiles(currentSessionId);
    const finalMessage = buildUserMessage(text, uploaded);

    promptInput.value = "";
    promptInput.style.height = "auto";
    toggleWelcomePanel(false);

    await runAssistantStream({
      userMessage: finalMessage,
      useAgent: shouldUseAgent(finalMessage, uploaded.length > 0),
    });
    // 从服务端加载消息（含正确 message id，便于后续编辑）
  } catch (err) {
    setStatus(t("status.sendFailed", { msg: err.message }));
  }
});

stopButton.addEventListener("click", async () => {
  forceStopStreamingUI();
  if (activeStreamAbort) {
    activeStreamAbort.abort();
  }
  try {
    if (currentSessionId) {
      await fetch(`/api/sessions/${currentSessionId}/cancel`, { method: "POST" });
    }
  } catch {
    /* ignore */
  }
  statusText.className = "status-text status-warn";
  setStatus(t("status.stopRequested"));
});

promptInput.addEventListener("input", () => {
  promptInput.style.height = "auto";
  promptInput.style.height = `${Math.min(promptInput.scrollHeight, 260)}px`;
});

promptInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

attachBtn.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  addPendingFiles(fileInput.files);
  fileInput.value = "";
});

composer.addEventListener("dragover", (e) => {
  e.preventDefault();
  composer.classList.add("dragover");
});
composer.addEventListener("dragleave", () => composer.classList.remove("dragover"));
composer.addEventListener("drop", (e) => {
  e.preventDefault();
  composer.classList.remove("dragover");
  addPendingFiles(e.dataTransfer.files);
});

newSessionBtn.addEventListener("click", async () => {
  if (isSharedView) return;
  try {
    forceStopStreamingUI();
    setStatus(t("status.creatingSession"));
    currentSessionId = await createSession({
      model: modelSelect.value || null,
      temperature: Number(tempInput.value || 0),
    });
    pendingFiles = [];
    renderAttachments();
    await fetchSessions();
    renderSessionList();
    await loadSessionView(currentSessionId);
    updateBrowserUrl(currentSessionId, false);
    setStatus("");
  } catch (err) {
    setStatus(t("status.createSessionFailed", { msg: err.message }));
  }
});

clearSessionBtn.addEventListener("click", async () => {
  if (!currentSessionId || isSharedView) return;
  if (!confirm(t("session.clearConfirm"))) return;
  const res = await fetch(`/api/sessions/${currentSessionId}/clear`, { method: "POST" });
  if (!res.ok) throw new Error(t("err.clearSession"));
  await fetchSessions();
  renderSessionList();
  await loadSessionView(currentSessionId);
});

refreshFilesBtn.addEventListener("click", async () => {
  if (!currentSessionId || isSharedView) return;
  filesPanelHint.textContent = t("files.refreshing");
  await loadWorkspaceFiles(currentSessionId);
});

shareBtn.addEventListener("click", async () => {
  if (!currentSessionId || isSharedView) return;
  await enableShare(currentSessionId);
  await navigator.clipboard.writeText(buildShareUrl(currentSessionId));
  shareStatus.textContent = t("toolbar.shareCopied");
  await fetchSessions();
  renderSessionList();
});

exitShareViewBtn.addEventListener("click", () => {
  window.location.href = "/";
});

if (lightboxClose) {
  lightboxClose.addEventListener("click", closeImageLightbox);
}
if (lightboxBackdrop) {
  lightboxBackdrop.addEventListener("click", closeImageLightbox);
}
if (editorAddTitle) {
  editorAddTitle.addEventListener("click", () => {
    addEditorText(editableFileStem(imageEditorState.sourceTitle), {
      role: "title",
      fontStyle: "bold",
      titlePosition: editorTitlePosition?.value || "top-center",
    });
  });
}
if (editorAddText) {
  editorAddText.addEventListener("click", () => addEditorText(t("image.newText")));
}
if (editorAddArrow) {
  editorAddArrow.addEventListener("click", addEditorArrow);
}
if (editorAddColorBlock) {
  editorAddColorBlock.addEventListener("click", addEditorColorBlock);
}
if (editorDelete) {
  editorDelete.disabled = true;
  editorDelete.addEventListener("click", () => {
    const node = imageEditorState.selectedNode;
    if (!node) return;
    node.destroy();
    setSelectedEditorNode(null);
  });
}
if (editorTextInput) {
  editorTextInput.addEventListener("input", () => {
    const node = imageEditorState.selectedNode;
    if (node && typeof node.text === "function") {
      node.text(editorTextInput.value);
      imageEditorState.layer?.batchDraw();
    }
  });
}
if (editorColorInput) {
  editorColorInput.addEventListener("input", () => {
    const node = imageEditorState.selectedNode;
    if (!node) return;
    if (typeof node.fill === "function") node.fill(editorColorInput.value);
    if (typeof node.stroke === "function") node.stroke(editorColorInput.value);
    imageEditorState.layer?.batchDraw();
  });
  editorColorInput.addEventListener("change", () => {
    if (imageEditorState.selectedNode) return;
    replaceRasterColor(imageEditorState.pickedRasterColor, editorColorInput.value);
  });
}
if (editorFontSizeInput) {
  editorFontSizeInput.addEventListener("input", () => {
    const node = imageEditorState.selectedNode;
    if (node && typeof node.fontSize === "function") {
      node.fontSize(Number(editorFontSizeInput.value || 24));
      imageEditorState.layer?.batchDraw();
    }
  });
}
if (editorTitlePosition) {
  editorTitlePosition.addEventListener("change", () => {
    applyTitlePosition(editorTitlePosition.value);
  });
}
if (editorSave) editorSave.addEventListener("click", saveImageEdit);
if (editorCancel) editorCancel.addEventListener("click", closeImageEditor);
if (editorClose) editorClose.addEventListener("click", closeImageEditor);
if (editorBackdrop) editorBackdrop.addEventListener("click", closeImageEditor);
if (plotlyLegendColorInput) {
  plotlyLegendColorInput.addEventListener("input", () => {
    applyPlotlyTraceColor(plotlyEditorState.selectedTrace, plotlyLegendColorInput.value);
  });
}
if (plotlyTraceSelect) {
  plotlyTraceSelect.addEventListener("change", () => {
    if (!plotlyTraceSelect.value) return;
    selectPlotlyTrace(Number(plotlyTraceSelect.value), { openPicker: false });
  });
}
if (plotlyEditorSave) plotlyEditorSave.addEventListener("click", savePlotlyEdit);
if (plotlyEditorCancel) plotlyEditorCancel.addEventListener("click", closePlotlyEditor);
if (plotlyEditorClose) plotlyEditorClose.addEventListener("click", closePlotlyEditor);
if (plotlyEditorBackdrop) plotlyEditorBackdrop.addEventListener("click", closePlotlyEditor);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && plotlyEditor && !plotlyEditor.classList.contains("hidden")) {
    closePlotlyEditor();
    return;
  }
  if (event.key === "Escape" && imageEditor && !imageEditor.classList.contains("hidden")) {
    closeImageEditor();
    return;
  }
  if (
    (event.key === "Delete" || event.key === "Backspace") &&
    imageEditor &&
    !imageEditor.classList.contains("hidden") &&
    imageEditorState.selectedNode &&
    document.activeElement !== editorTextInput
  ) {
    imageEditorState.selectedNode.destroy();
    setSelectedEditorNode(null);
    return;
  }
  if (event.key === "Escape" && imageLightbox && !imageLightbox.classList.contains("hidden")) {
    closeImageLightbox();
  }
});

function onLanguageChanged() {
  renderSessionList();
  if (appRuntime) renderRuntimeInfo(appRuntime);
  else if (runtimeInfo) runtimeInfo.textContent = t("runtime.detecting");
  initTools();
  if (currentSessionId && !isSharedView) {
    loadWorkspaceFiles(currentSessionId);
  } else if (!currentSessionId || isSharedView) {
    filesPanelHint.textContent = t("files.hint");
  }
}

(async () => {
  window.MassI18n.init();
  window.MassI18n.onLangChange(onLanguageChanged);
  // 先加载会话，不等待工具列表（/api/tools 可能较慢）
  forceStopStreamingUI();
  const params = getUrlParams();
  const sharedSessionId = params.get("session");

  const sideTasks = Promise.allSettled([
    initModels(),
    initTools(),
    initRuntime(),
  ]);

  try {
    if (sharedSessionId && params.get("view") === "shared") {
      await enterSharedView(sharedSessionId);
    } else {
      if (sharedSessionId) currentSessionId = sharedSessionId;
      await bootSessionsAndLoad();
    }
  } catch (err) {
    setStatus(t("status.pageLoadFailed", { msg: err.message }));
  }

  await sideTasks;
})();
