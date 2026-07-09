const modelSelect = document.getElementById("modelSelect");
const tempInput = document.getElementById("tempInput");
const messagesEl = document.getElementById("messages");
const form = document.getElementById("chatForm");
const promptInput = document.getElementById("promptInput");
const chatColorBtn = document.getElementById("chatColorBtn");
const chatColorBtnSwatch = document.getElementById("chatColorBtnSwatch");
const chatColorPopover = document.getElementById("chatColorPopover");
const chatColorNative = document.getElementById("chatColorNative");
const chatColorHexPreview = document.getElementById("chatColorHexPreview");
const chatColorPresets = document.getElementById("chatColorPresets");
const chatColorConfirm = document.getElementById("chatColorConfirm");
const chatColorCancel = document.getElementById("chatColorCancel");
const chatColorClose = document.getElementById("chatColorClose");
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
const editorEyedropper = document.getElementById("editorEyedropper");
const editorSourceColorSwatch = document.getElementById("editorSourceColorSwatch");
const editorRasterTargetColor = document.getElementById("editorRasterTargetColor");
const editorRasterTolerance = document.getElementById("editorRasterTolerance");
const editorRasterToleranceVal = document.getElementById("editorRasterToleranceVal");
const editorReplaceAllColors = document.getElementById("editorReplaceAllColors");
const editorUndo = document.getElementById("editorUndo");
const outputImageGalleryWrap = document.getElementById("outputImageGalleryWrap");
const openImageMergeBtn = document.getElementById("openImageMergeBtn");
const imageMergeEditor = document.getElementById("imageMergeEditor");
const imageMergeBackdrop = document.getElementById("imageMergeBackdrop");
const imageMergeClose = document.getElementById("imageMergeClose");
const imageMergePickList = document.getElementById("imageMergePickList");
const imageMergeCols = document.getElementById("imageMergeCols");
const imageMergeLabels = document.getElementById("imageMergeLabels");
const imageMergeAutoLayout = document.getElementById("imageMergeAutoLayout");
const imageMergeUndo = document.getElementById("imageMergeUndo");
const imageMergeStatus = document.getElementById("imageMergeStatus");
const imageMergeStageScaler = document.getElementById("imageMergeStageScaler");
const imageMergeStageHost = document.getElementById("imageMergeStageHost");
const imageMergeStage = document.getElementById("imageMergeStage");
const imageMergePreviewWrap = document.querySelector(".image-merge-preview-wrap");
const imageMergeZoomOut = document.getElementById("imageMergeZoomOut");
const imageMergeZoomIn = document.getElementById("imageMergeZoomIn");
const imageMergeZoomFit = document.getElementById("imageMergeZoomFit");
const imageMergeZoomLabel = document.getElementById("imageMergeZoomLabel");
const imageMergeCanvasSize = document.getElementById("imageMergeCanvasSize");
const imageMergeLabelFontSize = document.getElementById("imageMergeLabelFontSize");
const imageMergeCustomLabel = document.getElementById("imageMergeCustomLabel");
const imageMergeAddText = document.getElementById("imageMergeAddText");
const imageMergeTextInput = document.getElementById("imageMergeTextInput");
const imageMergeFontSize = document.getElementById("imageMergeFontSize");
const imageMergeDelete = document.getElementById("imageMergeDelete");
const imageMergeCancel = document.getElementById("imageMergeCancel");
const imageMergeSave = document.getElementById("imageMergeSave");
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
const plotlyEditorUndo = document.getElementById("plotlyEditorUndo");
const plotlyTitleFontSizeInput = document.getElementById("plotlyTitleFontSize");
const plotlyAxisFontSizeInput = document.getElementById("plotlyAxisFontSize");
const editorFontSizeLabel = document.getElementById("editorFontSizeLabel");
const plotAgentEditor = document.getElementById("plotAgentEditor");
const plotAgentEditorBackdrop = document.getElementById("plotAgentEditorBackdrop");
const plotAgentEditorClose = document.getElementById("plotAgentEditorClose");
const plotAgentEditorTitle = document.getElementById("plotAgentEditorTitle");
const plotAgentEditorHint = document.getElementById("plotAgentEditorHint");
const plotAgentInstruction = document.getElementById("plotAgentInstruction");
const plotAgentPreviewWrap = document.getElementById("plotAgentPreviewWrap");
const plotAgentEcharts = document.getElementById("plotAgentEcharts");
const plotAgentPreviewImg = document.getElementById("plotAgentPreviewImg");
const plotAgentEditorCancel = document.getElementById("plotAgentEditorCancel");
const plotAgentEditorApply = document.getElementById("plotAgentEditorApply");
const plotAgentEditorStatus = document.getElementById("plotAgentEditorStatus");
const mergeAgentEditor = document.getElementById("mergeAgentEditor");
const mergeAgentEditorBackdrop = document.getElementById("mergeAgentEditorBackdrop");
const mergeAgentEditorClose = document.getElementById("mergeAgentEditorClose");
const mergeAgentEditorTitle = document.getElementById("mergeAgentEditorTitle");
const mergeAgentEditorHint = document.getElementById("mergeAgentEditorHint");
const mergeAgentInstruction = document.getElementById("mergeAgentInstruction");
const mergeAgentPreviewWrap = document.getElementById("mergeAgentPreviewWrap");
const mergeAgentPreviewImg = document.getElementById("mergeAgentPreviewImg");
const mergeAgentEditorCancel = document.getElementById("mergeAgentEditorCancel");
const mergeAgentEditorApply = document.getElementById("mergeAgentEditorApply");
const mergeAgentEditorStatus = document.getElementById("mergeAgentEditorStatus");

const IMAGE_EXT_RE = /\.(png|jpe?g|gif|webp|svg)$/i;
const KONVA_ONLY_IMAGE_STEMS = new Set(["network_topology"]);
const AGENT_PLOT_STEM_PREFIXES = [
  "pca_plot",
  "plsda_plot",
  "volcano_plot",
  "family_size_distribution",
  "degree_distribution",
  "cosine_distribution",
];
const AGENT_PLOT_UNSUPPORTED_STEMS = new Set(["network_topology", "heatmap_top_vip"]);
const MERGE_CANVAS_BG = "#ffffff";
const MERGE_LAYOUT_GAP = 24;
const MERGE_SNAP_THRESHOLD = 10;
const CHAT_COLOR_PRESETS = [
  "#E64B35",
  "#4DBBD5",
  "#00A087",
  "#3C5488",
  "#F39B7F",
  "#8491B4",
  "#D62728",
  "#2CA02C",
  "#FF7F0E",
  "#9467BD",
  "#111827",
  "#B0B0B0",
];
let chatColorState = {
  open: false,
  replaceHash: false,
  hashIndex: -1,
  selected: "#4DBBD5",
};
const KONVA_UNDO_LIMIT = 40;
const PLOTLY_UNDO_LIMIT = 40;

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
  eyedropperActive: false,
};
let plotlyEditorState = {
  sourceRel: "",
  sourceTitle: "",
  selectedTrace: null,
};
let workspaceOutputImages = [];
let konvaHistory = [];
let konvaHistoryIndex = -1;
let plotlyHistory = [];
let plotlyHistoryIndex = -1;
let plotAgentState = {
  sourceRel: "",
  sourceTitle: "",
  echartsInstance: null,
};
let mergeAgentState = {
  sourceRel: "",
  sourceTitle: "",
};
let mergeHistory = [];
let mergeHistoryIndex = -1;
let imageMergeState = {
  stage: null,
  layer: null,
  transformer: null,
  selectedNode: null,
  selected: [],
  customLabels: {},
  canvasW: 1200,
  canvasH: 900,
  displayScale: 1,
  freeTextCount: 0,
  mergeDragStart: null,
  mergeDragAxis: null,
  viewZoom: 1,
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
  const images = (files || [])
    .filter((file) => isImagePath(file.name))
    .sort((a, b) => {
      const aMerged = String(a.name || "").startsWith("merged_figures/");
      const bMerged = String(b.name || "").startsWith("merged_figures/");
      if (aMerged !== bMerged) return aMerged ? -1 : 1;
      return 0;
    });
  workspaceOutputImages = images;
  if (outputImageGalleryWrap) {
    outputImageGalleryWrap.classList.toggle("hidden", images.length === 0);
  }
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
    const baseName = file.name.split("/").pop();
    title.textContent = baseName;
    title.title = file.name;
    if (String(file.name || "").startsWith("merged_figures/")) {
      const badge = document.createElement("span");
      badge.className = "output-image-merge-badge";
      badge.textContent = t("image.mergeBadge");
      title.prepend(badge, " ");
    }
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

    if (isAgentPlotEditable(file.name)) {
      const agentBtn = document.createElement("button");
      agentBtn.type = "button";
      agentBtn.className = "output-image-agent-edit secondary-btn small-btn";
      agentBtn.textContent = t("image.agentEdit");
      agentBtn.addEventListener("click", (event) => {
        event.stopPropagation();
        openPlotAgentEditor({
          rel: file.name,
          title: file.name.split("/").pop(),
        });
      });
      side.appendChild(agentBtn);
    }

    if (isMergedFigureRel(file.name)) {
      const mergeAgentBtn = document.createElement("button");
      mergeAgentBtn.type = "button";
      mergeAgentBtn.className = "output-image-merge-agent secondary-btn small-btn";
      mergeAgentBtn.textContent = t("image.mergeAgentEdit");
      mergeAgentBtn.addEventListener("click", (event) => {
        event.stopPropagation();
        openMergeAgentEditor({
          rel: file.name,
          title: file.name.split("/").pop(),
        });
      });
      side.appendChild(mergeAgentBtn);
    }

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
    eyedropperActive: false,
  };
  resetKonvaUndo();
  setEyedropperActive(false);
  if (editorStage) editorStage.innerHTML = "";
  if (editorStageScaler) {
    editorStageScaler.style.width = "";
    editorStageScaler.style.height = "";
    editorStageScaler.style.cursor = "";
  }
  if (editorTextInput) editorTextInput.value = "";
  if (editorTitlePosition) editorTitlePosition.value = "top-center";
  updateSourceColorSwatch(null);
  if (editorRasterToleranceVal && editorRasterTolerance) {
    editorRasterToleranceVal.textContent = editorRasterTolerance.value;
  }
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

function shouldUsePlotlyEditor(rel) {
  const base = String(rel || "").split("/").pop() || "";
  const stem = editableFileStem(base);
  return !KONVA_ONLY_IMAGE_STEMS.has(stem);
}

function isMergedFigureRel(rel) {
  return String(rel || "").startsWith("merged_figures/");
}

function hasMergeSidecar(rel) {
  return isMergedFigureRel(rel);
}

function isAgentPlotEditable(rel) {
  const base = String(rel || "").split("/").pop() || "";
  const stem = editableFileStem(base);
  if (AGENT_PLOT_UNSUPPORTED_STEMS.has(stem)) return false;
  return AGENT_PLOT_STEM_PREFIXES.some(
    (prefix) => stem === prefix || stem.startsWith(`${prefix}_`)
  );
}

/** 与 image_merge_registry.py 语义一致 — 拼图编辑 */
function shouldUseMergeFigureEdit(message) {
  const text = (message || "").trim();
  if (!text) return false;
  if (
    /改(?:一下)?拼图|调整(?:一下)?拼图|编辑拼图|修改拼图|更新拼图|拼图.{0,24}(?:标签|字号|字大小|列|间距|legend|label|font)|合并(?:后的|好的|完的)?图.{0,24}(?:标签|字号|列|间距)|merged_figures\/|merged_[\w-]+\.png|edit(?:ing)?\s+(?:the\s+)?(?:merged|composite)\s+(?:figure|image|plot)/i.test(
      text
    )
  ) {
    return true;
  }
  if (/拼图|合并图|merged\s+figure|composite\s+figure/i.test(text)) {
    if (/标签|字号|字大小|列|间距|legend|label|font\s*size|gap/i.test(text)) {
      if (
        !/合并.{0,80}(?:和|与|、|,|\+|以及|and).{0,80}(?:\.(?:png|jpe?g)|distribution|plot|figure|图)/i.test(
          text
        )
      ) {
        return true;
      }
    }
  }
  return false;
}

/** 与 image_merge_registry.py 语义一致 */
function shouldUseImageMerge(message) {
  const text = (message || "").trim();
  if (!text) return false;
  if (shouldUseMergeFigureEdit(text)) return true;
  if (
    /标题|颜色|色号|配色|#|改成|改为|改图|recolor|change\s+(?:the\s+)?title/i.test(text)
  ) {
    return false;
  }
  if (
    /合并(?:一下)?(?:图片|图|照片|子图|结果图|分析图|figure|figures|images?)|合并.{0,120}(?:和|与|、|,|\+|以及|and).{0,120}(?:\.(?:png|jpe?g|webp|gif)|图|plot|figure|image|distribution|diagram)|合并\s+[\w./-]+\.(?:png|jpe?g|webp|gif)|拼图|拼在一起|一键合并|merge\s+(?:the\s+)?(?:images?|figures?|plots?)|merge.{0,120}(?:and|&|,).{0,120}(?:\.(?:png|jpe?g|webp)|plot|figure|image|distribution)|combine\s+(?:the\s+)?(?:images?|figures?|plots?)/i.test(
      text
    )
  ) {
    return true;
  }
  if (/合并/.test(text) && /(?:和|与|、|,|\+|以及|and)/.test(text)) {
    if (/\.(?:png|jpe?g|webp|gif)\b/i.test(text)) return true;
    if (/cosine|degree|pca|volcano|distribution|heatmap|network|plot|figure|图/i.test(text)) {
      return true;
    }
  }
  return false;
}

/** 与 plot_edit_registry.py 语义一致 */
function shouldUsePlotEdit(message) {
  const text = (message || "").trim();
  if (!text) return false;
  if (/(?:进行|执行|跑|开始|继续).{0,12}分析/.test(text)) {
    if (!/标题|颜色|色号|配色|#|改成|改为|改图|字号|字体|直方图|分布图/.test(text)) {
      return false;
    }
  }
  if (
    /改图|修改(?:一下)?图|调整(?:一下)?图|更改?图|美化图|标题改|标题改为|标题改成|标题修改为|标题为|改(?:一下)?标题|修改.*标题|更换标题|颜色|色号|配色|调色|字体|字号|图例|用\s*#|#[0-9a-fA-F]{3,8}\b|改成|改为|换成|用.{0,8}色|直方图|分布图|重新绘|重绘|重新作图|edit\s+(?:the\s+)?plot|change\s+(?:the\s+)?title|recolor|font\s+size|plot\s+style/i.test(
      text
    )
  ) {
    return true;
  }
  const hasPlotRef =
    /pca|plsda|pls-da|主成分|火山|volcano|余弦|cosine|相似度|度数|分布图|pca_plot|volcano_plot|cosine_distribution/i.test(
      text
    );
  const hasStyle =
    /标题|字号|字体|颜色|色号|配色|图例|改成|改为|换成|用\s*#|#[0-9a-fA-F]{3,8}/i.test(text);
  return hasPlotRef && hasStyle;
}

function echartsCompanionRel(imageRel) {
  return String(imageRel || "").replace(/\.(png|jpe?g|gif|webp|svg)$/i, ".echarts.json");
}

function updateSourceColorSwatch(color) {
  if (!editorSourceColorSwatch) return;
  if (!color) {
    editorSourceColorSwatch.textContent = "—";
    editorSourceColorSwatch.style.background = "#fff";
    editorSourceColorSwatch.style.color = "";
    return;
  }
  const hex = rgbToHex(color.r, color.g, color.b);
  editorSourceColorSwatch.textContent = hex;
  editorSourceColorSwatch.style.background = hex;
  editorSourceColorSwatch.style.color = "#fff";
}

function rasterToleranceValue() {
  return Number(editorRasterTolerance?.value || 55);
}

function cloneImageData(imageData) {
  if (!imageData) return null;
  return new ImageData(
    new Uint8ClampedArray(imageData.data),
    imageData.width,
    imageData.height
  );
}

function captureKonvaSnapshot() {
  const { rasterCtx, rasterCanvas } = imageEditorState;
  const raster =
    rasterCtx && rasterCanvas
      ? cloneImageData(rasterCtx.getImageData(0, 0, rasterCanvas.width, rasterCanvas.height))
      : null;
  return {
    raster,
    objects: JSON.parse(JSON.stringify(serializeEditableState().objects || [])),
    pickedColor: imageEditorState.pickedRasterColor
      ? { ...imageEditorState.pickedRasterColor }
      : null,
  };
}

function konvaSnapshotsEqual(a, b) {
  if (!a || !b) return false;
  if (JSON.stringify(a.objects) !== JSON.stringify(b.objects)) return false;
  if (Boolean(a.pickedColor) !== Boolean(b.pickedColor)) return false;
  if (!a.raster || !b.raster) return !a.raster && !b.raster;
  if (a.raster.data.length !== b.raster.data.length) return false;
  for (let i = 0; i < a.raster.data.length; i += 128) {
    if (a.raster.data[i] !== b.raster.data[i]) return false;
  }
  return true;
}

function refreshKonvaRasterImage() {
  const { imageNode, rasterCanvas, layer } = imageEditorState;
  if (!imageNode || !rasterCanvas) return;
  if (typeof imageNode.clearCache === "function") imageNode.clearCache();
  imageNode.image(null);
  imageNode.image(rasterCanvas);
  layer?.batchDraw();
}

function commitKonvaState() {
  if (!imageEditorState.layer) return;
  const snap = captureKonvaSnapshot();
  konvaHistory = konvaHistory.slice(0, konvaHistoryIndex + 1);
  if (konvaHistoryIndex >= 0 && konvaSnapshotsEqual(konvaHistory[konvaHistoryIndex], snap)) {
    if (editorUndo) editorUndo.disabled = konvaHistoryIndex <= 0;
    return;
  }
  konvaHistory.push(snap);
  if (konvaHistory.length > KONVA_UNDO_LIMIT) konvaHistory.shift();
  konvaHistoryIndex = konvaHistory.length - 1;
  if (editorUndo) editorUndo.disabled = konvaHistoryIndex <= 0;
}

function restoreKonvaSnapshot(snap) {
  if (!snap || !imageEditorState.layer) return;
  const { rasterCtx, rasterCanvas } = imageEditorState;
  if (snap.raster && rasterCtx && rasterCanvas) {
    rasterCtx.putImageData(cloneImageData(snap.raster), 0, 0);
    refreshKonvaRasterImage();
  }
  imageEditorState.layer.children.slice().forEach((node) => {
    const name = node.name?.();
    if (name && String(name).startsWith("editable-")) node.destroy();
  });
  (snap.objects || []).forEach((obj) => restoreEditableObject(obj, { silent: true }));
  imageEditorState.pickedRasterColor = snap.pickedColor || null;
  updateSourceColorSwatch(imageEditorState.pickedRasterColor);
  setSelectedEditorNode(null);
  imageEditorState.layer.batchDraw();
}

function undoKonvaEdit() {
  commitKonvaOverlayIfDirty();
  if (konvaHistoryIndex <= 0) {
    setEditorStatus(t("image.undoEmpty"));
    return;
  }
  konvaHistoryIndex -= 1;
  restoreKonvaSnapshot(konvaHistory[konvaHistoryIndex]);
  if (editorUndo) editorUndo.disabled = konvaHistoryIndex <= 0;
  setEditorStatus(t("image.undoDone"));
}

function resetKonvaUndo() {
  konvaHistory = [];
  konvaHistoryIndex = -1;
  if (editorUndo) editorUndo.disabled = true;
}

function capturePlotlySnapshot() {
  if (!plotlyChart) return null;
  return {
    data: JSON.parse(JSON.stringify(plotlyChart.data || [])),
    layout: JSON.parse(JSON.stringify(plotlyChart.layout || {})),
  };
}

function commitPlotlyState() {
  const snap = capturePlotlySnapshot();
  if (!snap) return;
  plotlyHistory = plotlyHistory.slice(0, plotlyHistoryIndex + 1);
  const current = plotlyHistory[plotlyHistoryIndex];
  if (current && JSON.stringify(current) === JSON.stringify(snap)) {
    if (plotlyEditorUndo) plotlyEditorUndo.disabled = plotlyHistoryIndex <= 0;
    return;
  }
  plotlyHistory.push(snap);
  if (plotlyHistory.length > PLOTLY_UNDO_LIMIT) plotlyHistory.shift();
  plotlyHistoryIndex = plotlyHistory.length - 1;
  if (plotlyEditorUndo) plotlyEditorUndo.disabled = plotlyHistoryIndex <= 0;
}

function restorePlotlySnapshot(snap) {
  if (!plotlyChart || !window.Plotly || !snap) return;
  Plotly.react(plotlyChart, snap.data || [], snap.layout || {}, {
    responsive: true,
    displayModeBar: false,
    editable: true,
    edits: {
      annotationPosition: true,
      annotationText: true,
      legendPosition: true,
      legendText: true,
      titleText: true,
      axisTitleText: true,
    },
  }).then(() => {
    bindPlotlyLegendColorPicker();
    populatePlotlyTraceSelect(snap.data || []);
    syncPlotlyFontControlsFromLayout();
  });
}

function undoPlotlyEdit() {
  if (plotlyHistoryIndex <= 0) {
    setPlotlyEditorStatus(t("image.undoEmpty"));
    return;
  }
  plotlyHistoryIndex -= 1;
  restorePlotlySnapshot(plotlyHistory[plotlyHistoryIndex]);
  if (plotlyEditorUndo) plotlyEditorUndo.disabled = plotlyHistoryIndex <= 0;
  setPlotlyEditorStatus(t("image.undoDone"));
}

function resetPlotlyUndo() {
  plotlyHistory = [];
  plotlyHistoryIndex = -1;
  if (plotlyEditorUndo) plotlyEditorUndo.disabled = true;
}

function plotlyEditableTitleAnnotationIndex(layout = plotlyChart?.layout) {
  const annotations = layout?.annotations;
  if (!Array.isArray(annotations)) return -1;
  return annotations.findIndex((item) => item?.name === "editable-title");
}

function syncPlotlyFontControlsFromLayout() {
  const layout = plotlyChart?.layout || {};
  const annIdx = plotlyEditableTitleAnnotationIndex(layout);
  let titleSize = 18;
  if (annIdx >= 0) {
    titleSize = layout.annotations[annIdx]?.font?.size || 18;
  } else if (layout.title?.font?.size != null) {
    titleSize = layout.title.font.size;
  } else if (typeof layout.title === "object" && layout.title?.font?.size != null) {
    titleSize = layout.title.font.size;
  }
  const axisSize =
    layout.xaxis?.title?.font?.size ??
    layout.yaxis?.title?.font?.size ??
    14;
  if (plotlyTitleFontSizeInput) plotlyTitleFontSizeInput.value = String(titleSize);
  if (plotlyAxisFontSizeInput) plotlyAxisFontSizeInput.value = String(axisSize);
}

async function applyPlotlyFontSizes({ titleSize, axisSize } = {}) {
  if (!plotlyChart || !window.Plotly) return;
  const relayoutPatch = {};
  if (titleSize != null) {
    const annIdx = plotlyEditableTitleAnnotationIndex();
    if (annIdx >= 0) {
      relayoutPatch[`annotations[${annIdx}].font.size`] = titleSize;
    } else {
      relayoutPatch["title.font.size"] = titleSize;
    }
  }
  if (axisSize != null) {
    relayoutPatch["xaxis.title.font.size"] = axisSize;
    relayoutPatch["yaxis.title.font.size"] = axisSize;
  }
  if (!Object.keys(relayoutPatch).length) return;
  await Plotly.relayout(plotlyChart, relayoutPatch);
  commitPlotlyState();
  syncPlotlyFontControlsFromLayout();
  setPlotlyEditorStatus(t("image.plotlyFontApplied"));
}

function setEyedropperActive(active) {
  imageEditorState.eyedropperActive = Boolean(active);
  if (editorEyedropper) {
    editorEyedropper.classList.toggle("active", imageEditorState.eyedropperActive);
    editorEyedropper.textContent = imageEditorState.eyedropperActive
      ? t("image.eyedropperActive")
      : t("image.eyedropperOff");
  }
  if (editorStageScaler) {
    editorStageScaler.style.cursor = imageEditorState.eyedropperActive ? "crosshair" : "";
  }
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
  if (editorFontSizeLabel) {
    const isTitle = node?.name?.() === "editable-title";
    editorFontSizeLabel.textContent = isTitle ? t("image.titleFontSize") : t("image.fontSize");
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
  node.on("dragend", () => commitKonvaState());
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
  updateSourceColorSwatch(color);
  setSelectedEditorNode(null);
  setEyedropperActive(false);
  setEditorStatus(t("image.rasterColorPicked", { color: rgbToHex(r, g, b) }));
  return color;
}

function replaceRasterColor(targetColor, replacementHex, tolerance = rasterToleranceValue()) {
  const replacement = hexToRgb(replacementHex);
  const { rasterCtx, rasterCanvas, imageNode } = imageEditorState;
  if (!targetColor || !replacement || !rasterCtx || !rasterCanvas || !imageNode) return 0;

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
  refreshKonvaRasterImage();
  imageEditorState.pickedRasterColor = replacement;
  updateSourceColorSwatch(replacement);
  commitKonvaState();
  setEditorStatus(t("image.rasterColorApplied", { count: changed }));
  return changed;
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
  if (!options.silent) {
    setSelectedEditorNode(node);
    commitKonvaState();
  }
  return node;
}

function addEditorArrow(options = {}) {
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
  if (!options.silent) {
    setSelectedEditorNode(node);
    commitKonvaState();
  }
  return node;
}

function addEditorColorBlock(options = {}) {
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
  if (!options.silent) {
    setSelectedEditorNode(node);
    commitKonvaState();
  }
  return node;
}

function restoreEditableObject(obj, options = {}) {
  if (!obj || !imageEditorState.layer) return;
  if (obj.type === "text" || obj.type === "title") {
    addEditorText(obj.text || "", {
      silent: true,
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
    const node = addEditorArrow({ silent: true });
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
    const node = addEditorColorBlock({ silent: true });
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
      if (!imageEditorState.eyedropperActive) return;
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
    commitKonvaState();
    setEditorStatus(t("image.ready"));
  };
  img.onerror = () => setEditorStatus(t("image.loadFail"), "error");
  img.src = `${url}${url.includes("?") ? "&" : "?"}edit=${Date.now()}`;
}

async function openImageEditor({ url, rel, title }) {
  if (shouldUsePlotlyEditor(rel)) {
    const plotlyFigure = await fetchPlotlyFigure(rel);
    if (plotlyFigure) {
      openPlotlyEditor({ rel, title, figure: plotlyFigure });
      return;
    }
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
  Plotly.restyle(plotlyChart, update, [traceIndex]).then(() => {
    commitPlotlyState();
    setPlotlyEditorStatus(t("image.plotlyColorApplied", { name: trace.name || traceIndex + 1 }));
  });
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
  plotlyChart.on("plotly_legenddoubleclick", () => false);
}

function plotlyTitleText(layout) {
  const title = layout?.title;
  if (typeof title === "string") return title;
  if (title && typeof title.text === "string") return title.text;
  return "";
}

function sanitizePlotlyFigure(figure) {
  const raw = figure && typeof figure === "object" ? figure : {};
  const data = JSON.parse(JSON.stringify(raw.data || []));
  const layout = normalizePlotlyLayoutForEditing(raw.layout || {});

  delete layout.width;
  delete layout.height;
  delete layout.template;
  delete layout.autosize;
  layout.autosize = true;
  layout.margin = layout.margin || { l: 60, r: 30, t: 80, b: 60 };

  if (Array.isArray(layout.shapes)) {
    layout.shapes = layout.shapes.filter(
      (shape) =>
        !(
          shape?.type === "rect" &&
          shape?.xref === "paper" &&
          shape?.yref === "paper" &&
          Number(shape?.x0) === 0 &&
          Number(shape?.x1) === 1
        )
    );
  }

  return { data, layout };
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
  resetPlotlyUndo();
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

  const sanitized = sanitizePlotlyFigure(figure);
  const layout = {
    ...sanitized.layout,
    autosize: true,
    margin: sanitized.layout?.margin || { l: 60, r: 30, t: 80, b: 60 },
  };
  Plotly.react(plotlyChart, sanitized.data || [], layout, {
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
    syncPlotlyFontControlsFromLayout();
    commitPlotlyState();
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
  resetPlotlyUndo();
  setPlotlyEditorStatus("");
}

function setPlotAgentEditorStatus(text, kind = "") {
  if (!plotAgentEditorStatus) return;
  plotAgentEditorStatus.textContent = text || "";
  plotAgentEditorStatus.classList.toggle("error", kind === "error");
}

function disposePlotAgentEcharts() {
  if (plotAgentState.echartsInstance) {
    plotAgentState.echartsInstance.dispose();
    plotAgentState.echartsInstance = null;
  }
  if (plotAgentEcharts) plotAgentEcharts.innerHTML = "";
}

function openPlotAgentEditor({ rel, title }) {
  if (!plotAgentEditor) return;
  closeImageLightbox();
  closeImageEditor();
  closePlotlyEditor();
  disposePlotAgentEcharts();
  plotAgentState.sourceRel = rel;
  plotAgentState.sourceTitle = title || rel.split("/").pop();
  if (plotAgentInstruction) plotAgentInstruction.value = "";
  if (plotAgentPreviewWrap) plotAgentPreviewWrap.classList.add("hidden");
  if (plotAgentPreviewImg) {
    plotAgentPreviewImg.classList.add("hidden");
    plotAgentPreviewImg.removeAttribute("src");
  }
  if (plotAgentEditorTitle) {
    plotAgentEditorTitle.textContent = t("image.plotAgentTitle", {
      name: plotAgentState.sourceTitle,
    });
  }
  if (plotAgentEditorHint) plotAgentEditorHint.textContent = t("image.plotAgentHint");
  plotAgentEditor.classList.remove("hidden");
  plotAgentEditor.setAttribute("aria-hidden", "false");
  setPlotAgentEditorStatus("");
}

function closePlotAgentEditor() {
  if (!plotAgentEditor) return;
  plotAgentEditor.classList.add("hidden");
  plotAgentEditor.setAttribute("aria-hidden", "true");
  disposePlotAgentEcharts();
  plotAgentState = { sourceRel: "", sourceTitle: "", echartsInstance: null };
  setPlotAgentEditorStatus("");
}

async function renderPlotAgentPreview(result) {
  if (!plotAgentPreviewWrap) return;
  plotAgentPreviewWrap.classList.remove("hidden");
  disposePlotAgentEcharts();

  const fileRel = result?.file?.name;
  const echartsRel = result?.echarts?.name;
  if (echartsRel && currentSessionId && window.echarts && plotAgentEcharts) {
    try {
      const url = workspaceFileUrl(currentSessionId, echartsRel);
      const res = await fetch(url);
      if (res.ok) {
        const option = await res.json();
        plotAgentState.echartsInstance = window.echarts.init(plotAgentEcharts);
        plotAgentState.echartsInstance.setOption(option, true);
        if (plotAgentPreviewImg) plotAgentPreviewImg.classList.add("hidden");
        return;
      }
    } catch {
      /* fallback to PNG */
    }
  }

  if (fileRel && currentSessionId && plotAgentPreviewImg) {
    const url = workspaceFileUrl(currentSessionId, fileRel);
    if (url) {
      plotAgentPreviewImg.src = `${url}&_=${Date.now()}`;
      plotAgentPreviewImg.classList.remove("hidden");
    }
  }
}

async function submitPlotAgentEdit() {
  if (!currentSessionId || !plotAgentState.sourceRel) return;
  const instruction = (plotAgentInstruction?.value || "").trim();
  if (!instruction) {
    setPlotAgentEditorStatus(t("image.plotAgentFail", { msg: "请先输入改图要求" }), "error");
    return;
  }
  try {
    setPlotAgentEditorStatus(t("image.plotAgentWorking"));
    if (plotAgentEditorApply) plotAgentEditorApply.disabled = true;
    const res = await fetch(`/api/sessions/${currentSessionId}/plot-edits/agent`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_rel: plotAgentState.sourceRel,
        instruction,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || t("image.plotAgentFail", { msg: "request failed" }));
    await renderPlotAgentPreview(data);
    await loadWorkspaceFiles(currentSessionId);
    const name = data.file?.name?.split("/").pop() || "";
    setPlotAgentEditorStatus(t("image.plotAgentDone", { name }));
    setStatus(t("image.plotAgentDone", { name }));
  } catch (err) {
    setPlotAgentEditorStatus(t("image.plotAgentFail", { msg: err.message }), "error");
  } finally {
    if (plotAgentEditorApply) plotAgentEditorApply.disabled = false;
  }
}

function setMergeAgentEditorStatus(text, kind = "") {
  if (!mergeAgentEditorStatus) return;
  mergeAgentEditorStatus.textContent = text || "";
  mergeAgentEditorStatus.classList.toggle("error", kind === "error");
}

function openMergeAgentEditor({ rel, title }) {
  if (!mergeAgentEditor) return;
  if (!isMergedFigureRel(rel)) {
    setStatus(t("image.mergeAgentNeedSidecar"));
    return;
  }
  mergeAgentState.sourceRel = rel;
  mergeAgentState.sourceTitle = title || rel.split("/").pop();
  if (mergeAgentInstruction) mergeAgentInstruction.value = "";
  if (mergeAgentEditorTitle) {
    mergeAgentEditorTitle.textContent = t("image.mergeAgentTitle", {
      name: mergeAgentState.sourceTitle,
    });
  }
  if (mergeAgentEditorHint) mergeAgentEditorHint.textContent = t("image.mergeAgentHint");
  if (mergeAgentPreviewImg && currentSessionId) {
    const url = workspaceFileUrl(currentSessionId, rel);
    if (url) {
      mergeAgentPreviewImg.src = `${url}&_=${Date.now()}`;
      mergeAgentPreviewImg.classList.remove("hidden");
    }
  }
  if (mergeAgentPreviewWrap) mergeAgentPreviewWrap.classList.remove("hidden");
  mergeAgentEditor.classList.remove("hidden");
  mergeAgentEditor.setAttribute("aria-hidden", "false");
  setMergeAgentEditorStatus("");
}

function closeMergeAgentEditor() {
  if (!mergeAgentEditor) return;
  mergeAgentEditor.classList.add("hidden");
  mergeAgentEditor.setAttribute("aria-hidden", "true");
  mergeAgentState = { sourceRel: "", sourceTitle: "" };
  setMergeAgentEditorStatus("");
}

async function submitMergeAgentEdit() {
  if (!currentSessionId || !mergeAgentState.sourceRel) return;
  const instruction = (mergeAgentInstruction?.value || "").trim();
  if (!instruction) {
    setMergeAgentEditorStatus(t("image.mergeAgentFail", { msg: "请先输入改拼图要求" }), "error");
    return;
  }
  try {
    setMergeAgentEditorStatus(t("image.mergeAgentWorking"));
    if (mergeAgentEditorApply) mergeAgentEditorApply.disabled = true;
    const res = await fetch(`/api/sessions/${currentSessionId}/image-merge/edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_rel: mergeAgentState.sourceRel,
        instruction,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || t("image.mergeAgentFail", { msg: "request failed" }));
    if (mergeAgentPreviewImg && data.file?.name && currentSessionId) {
      const url = workspaceFileUrl(currentSessionId, data.file.name);
      if (url) mergeAgentPreviewImg.src = `${url}&_=${Date.now()}`;
    }
    await loadWorkspaceFiles(currentSessionId);
    const name = data.file?.name?.split("/").pop() || "";
    setMergeAgentEditorStatus(t("image.mergeAgentDone", { name }));
    setStatus(t("image.mergeAgentDone", { name }));
  } catch (err) {
    setMergeAgentEditorStatus(t("image.mergeAgentFail", { msg: err.message }), "error");
  } finally {
    if (mergeAgentEditorApply) mergeAgentEditorApply.disabled = false;
  }
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

function captureMergeConfig() {
  return {
    selected: [...imageMergeState.selected],
    cols: imageMergeCols?.value || "auto",
    labels: imageMergeLabels?.value || "upper",
    labelFontSize: Number(imageMergeLabelFontSize?.value || 28),
    customLabels: { ...imageMergeState.customLabels },
    nodes: serializeMergeNodes(),
    canvasW: imageMergeState.canvasW,
    canvasH: imageMergeState.canvasH,
  };
}

function serializeMergeNodes() {
  const nodes = [];
  imageMergeState.layer?.children?.forEach((node) => {
    const name = node.name?.() || "";
    if (!name || name === "merge-bg" || node.getClassName?.() === "Transformer") return;
    const base = {
      name,
      x: node.x(),
      y: node.y(),
      rotation: node.rotation?.() || 0,
    };
    if (name.startsWith("merge-panel-")) {
      nodes.push({
        ...base,
        type: "panel",
        rel: node.getAttr("panelRel") || name.replace("merge-panel-", ""),
        scaleX: node.scaleX(),
        scaleY: node.scaleY(),
      });
    } else if (name.startsWith("merge-label-")) {
      nodes.push({
        ...base,
        type: "label",
        rel: node.getAttr("panelRel") || name.replace("merge-label-", ""),
        text: node.text?.() || "",
        fontSize: node.fontSize?.() || 28,
        fill: node.fill?.() || "#111827",
      });
    } else if (name.startsWith("merge-text-")) {
      nodes.push({
        ...base,
        type: "text",
        text: node.text?.() || "",
        fontSize: node.fontSize?.() || 24,
        fill: node.fill?.() || "#111827",
      });
    }
  });
  return nodes;
}

function commitMergeState() {
  if (!imageMergeState.layer) return;
  const snap = captureMergeConfig();
  mergeHistory = mergeHistory.slice(0, mergeHistoryIndex + 1);
  const last = mergeHistory[mergeHistoryIndex];
  if (last && JSON.stringify(last) === JSON.stringify(snap)) {
    if (imageMergeUndo) imageMergeUndo.disabled = mergeHistoryIndex <= 0;
    return;
  }
  mergeHistory.push(snap);
  if (mergeHistory.length > 30) mergeHistory.shift();
  mergeHistoryIndex = mergeHistory.length - 1;
  if (imageMergeUndo) imageMergeUndo.disabled = mergeHistoryIndex <= 0;
}

function undoMergeEdit() {
  if (mergeHistoryIndex <= 0) {
    if (imageMergeStatus) imageMergeStatus.textContent = t("image.undoEmpty");
    return;
  }
  mergeHistoryIndex -= 1;
  restoreMergeConfig(mergeHistory[mergeHistoryIndex]).catch((err) => {
    if (imageMergeStatus) imageMergeStatus.textContent = err.message;
  });
  if (imageMergeUndo) imageMergeUndo.disabled = mergeHistoryIndex <= 0;
  if (imageMergeStatus) imageMergeStatus.textContent = t("image.undoDone");
}

function resetMergeHistory() {
  mergeHistory = [];
  mergeHistoryIndex = -1;
  if (imageMergeUndo) imageMergeUndo.disabled = true;
}

function applyMergeConfig(cfg) {
  if (!cfg || !imageMergePickList) return Promise.resolve();
  imageMergeState.selected = [...(cfg.selected || [])];
  renderImageMergePickList();
  if (imageMergeCols) imageMergeCols.value = cfg.cols || "auto";
  if (imageMergeLabels) imageMergeLabels.value = cfg.labels || "upper";
  if (imageMergeLabelFontSize) imageMergeLabelFontSize.value = String(cfg.labelFontSize ?? 28);
  imageMergeState.customLabels = { ...(cfg.customLabels || {}) };
  updateMergeCustomLabelRow();
  return restoreMergeNodes(cfg);
}

function restoreMergeConfig(cfg) {
  return applyMergeConfig(cfg);
}

function mergePanelLabel(index, mode) {
  if (mode === "none") return "";
  if (mode === "num") return String(index + 1);
  if (mode === "lower") return String.fromCharCode(97 + (index % 26));
  return String.fromCharCode(65 + (index % 26));
}

function mergeLabelText(index, rel, mode) {
  if (mode === "none") return "";
  if (mode === "custom") {
    return imageMergeState.customLabels[rel] || mergePanelLabel(index, "upper");
  }
  return mergePanelLabel(index, mode);
}

function loadImageElement(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("load failed"));
    img.src = url;
  });
}

function updateMergeCanvasSizeLabel() {
  const w = imageMergeState.canvasW || 0;
  const h = imageMergeState.canvasH || 0;
  if (imageMergeCanvasSize) {
    imageMergeCanvasSize.textContent =
      w > 0 && h > 0 ? t("image.mergeCanvasSize", { w, h }) : "—";
  }
}

function fitMergeStageDisplay(natW, natH) {
  imageMergeState.canvasW = natW;
  imageMergeState.canvasH = natH;
  if (imageMergeStage) {
    imageMergeStage.style.width = `${natW}px`;
    imageMergeStage.style.height = `${natH}px`;
    imageMergeStage.style.transform = "";
  }
  applyMergeViewZoom();
  updateMergeCanvasSizeLabel();
  return imageMergeState.viewZoom || 1;
}

function updateMergeZoomLabel() {
  if (imageMergeZoomLabel) {
    imageMergeZoomLabel.textContent = `${Math.round((imageMergeState.viewZoom || 1) * 100)}%`;
  }
}

function applyMergeViewZoom() {
  const zoom = imageMergeState.viewZoom || 1;
  const w = imageMergeState.canvasW || 800;
  const h = imageMergeState.canvasH || 600;
  const stage = imageMergeState.stage;
  if (stage) {
    stage.scale({ x: 1, y: 1 });
    stage.width(w);
    stage.height(h);
    stage.batchDraw();
  }
  if (imageMergeStageHost) {
    imageMergeStageHost.style.width = `${Math.ceil(w * zoom)}px`;
    imageMergeStageHost.style.height = `${Math.ceil(h * zoom)}px`;
  }
  if (imageMergeStageScaler) {
    imageMergeStageScaler.style.width = `${w}px`;
    imageMergeStageScaler.style.height = `${h}px`;
    imageMergeStageScaler.style.transform = `scale(${zoom})`;
    imageMergeStageScaler.style.transformOrigin = "top left";
  }
  imageMergeState.displayScale = zoom;
  updateMergeZoomLabel();
}

function setMergeViewZoom(zoom, { status = true } = {}) {
  imageMergeState.viewZoom = Math.max(0.05, Math.min(3, zoom));
  applyMergeViewZoom();
  if (status && imageMergeStatus) {
    imageMergeStatus.textContent = t("image.mergeZoomApplied", {
      pct: Math.round(imageMergeState.viewZoom * 100),
    });
  }
}

function fitMergeViewToPanel() {
  const wrap = imageMergePreviewWrap;
  const w = imageMergeState.canvasW || 800;
  const h = imageMergeState.canvasH || 600;
  if (!wrap || !w || !h) return;
  const pad = 28;
  const toolbar = 44;
  const maxW = Math.max(120, wrap.clientWidth - pad);
  const maxH = Math.max(120, wrap.clientHeight - pad - toolbar);
  const zoom = Math.min(1, maxW / w, maxH / h);
  setMergeViewZoom(Math.max(0.05, zoom), { status: false });
}

function getMergeContentBounds(padding = 24) {
  const layer = imageMergeState.layer;
  if (!layer) {
    return { minX: 0, minY: 0, maxX: imageMergeState.canvasW || 800, maxY: imageMergeState.canvasH || 600 };
  }
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  let hasContent = false;
  layer.children?.forEach((node) => {
    const name = node.name?.() || "";
    if (!name || name === "merge-bg" || node.getClassName?.() === "Transformer") return;
    const rect = node.getClientRect({ skipTransform: false });
    if (!rect.width && !rect.height) return;
    hasContent = true;
    minX = Math.min(minX, rect.x);
    minY = Math.min(minY, rect.y);
    maxX = Math.max(maxX, rect.x + rect.width);
    maxY = Math.max(maxY, rect.y + rect.height);
  });
  if (!hasContent) {
    return { minX: 0, minY: 0, maxX: imageMergeState.canvasW || 800, maxY: imageMergeState.canvasH || 600 };
  }
  return {
    minX: minX - padding,
    minY: minY - padding,
    maxX: maxX + padding,
    maxY: maxY + padding,
  };
}

function resizeMergeCanvas(width, height) {
  const w = Math.max(100, Math.ceil(width));
  const h = Math.max(100, Math.ceil(height));
  imageMergeState.canvasW = w;
  imageMergeState.canvasH = h;
  if (imageMergeState.stage) {
    imageMergeState.stage.scale({ x: 1, y: 1 });
    imageMergeState.stage.width(w);
    imageMergeState.stage.height(h);
  }
  const bg = imageMergeState.layer?.findOne((node) => node.name() === "merge-bg");
  if (bg) {
    bg.width(w);
    bg.height(h);
    bg.fill(MERGE_CANVAS_BG);
    bg.moveToBottom();
  }
  fitMergeStageDisplay(w, h);
  imageMergeState.layer?.batchDraw();
  return { w, h };
}

function fitMergeCanvasToContent(padding = 32) {
  const bounds = getMergeContentBounds(padding);
  const shiftX = bounds.minX < 0 ? -bounds.minX : 0;
  const shiftY = bounds.minY < 0 ? -bounds.minY : 0;
  if (shiftX || shiftY) {
    imageMergeState.layer?.children?.forEach((node) => {
      const name = node.name?.() || "";
      if (!name || name === "merge-bg" || node.getClassName?.() === "Transformer") return;
      node.position({ x: node.x() + shiftX, y: node.y() + shiftY });
    });
  }
  const width = Math.ceil(bounds.maxX + shiftX);
  const height = Math.ceil(bounds.maxY + shiftY);
  resizeMergeCanvas(width, height);
}

function exportMergeStagePng() {
  const layer = imageMergeState.layer;
  if (!layer) return "";
  setSelectedMergeNode(null);
  clearMergeSnapGuides();
  fitMergeCanvasToContent(32);
  const w = imageMergeState.canvasW;
  const h = imageMergeState.canvasH;
  const bgColor = MERGE_CANVAS_BG;
  const bg = layer.findOne((node) => node.name() === "merge-bg");
  if (bg) {
    bg.width(w);
    bg.height(h);
    bg.fill(bgColor);
    bg.moveToBottom();
  }
  const transformer = imageMergeState.transformer;
  const transformerVisible = transformer?.visible() !== false;
  if (transformer) transformer.visible(false);
  layer.batchDraw();
  const konvaCanvas = layer.toCanvas({
    x: 0,
    y: 0,
    width: w,
    height: h,
    pixelRatio: 1,
  });
  if (transformer) transformer.visible(transformerVisible);
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = bgColor;
  ctx.fillRect(0, 0, w, h);
  ctx.imageSmoothingEnabled = true;
  if (ctx.imageSmoothingQuality) ctx.imageSmoothingQuality = "high";
  ctx.drawImage(konvaCanvas, 0, 0);
  return canvas.toDataURL("image/png");
}

function destroyMergeStage() {
  if (imageMergeState.stage) {
    imageMergeState.stage.destroy();
  }
  imageMergeState.stage = null;
  imageMergeState.layer = null;
  imageMergeState.transformer = null;
  imageMergeState.selectedNode = null;
  imageMergeState.viewZoom = 1;
  if (imageMergeStage) imageMergeStage.innerHTML = "";
  if (imageMergeStageScaler) {
    imageMergeStageScaler.style.width = "";
    imageMergeStageScaler.style.height = "";
    imageMergeStageScaler.style.transform = "";
  }
  if (imageMergeStageHost) {
    imageMergeStageHost.style.width = "";
    imageMergeStageHost.style.height = "";
  }
}

function getSelectedPanelRel() {
  const node = imageMergeState.selectedNode;
  if (!node) return null;
  const name = node.name?.() || "";
  if (node.getAttr?.("panelRel")) return node.getAttr("panelRel");
  if (name.startsWith("merge-panel-")) return name.replace("merge-panel-", "");
  if (name.startsWith("merge-label-")) return name.replace("merge-label-", "");
  return null;
}

function setSelectedMergeNode(node) {
  imageMergeState.selectedNode = node || null;
  if (imageMergeState.transformer) {
    const canTransform =
      node &&
      (String(node.name?.() || "").startsWith("merge-panel-") ||
        String(node.name?.() || "").startsWith("merge-text-") ||
        String(node.name?.() || "").startsWith("merge-label-"));
    imageMergeState.transformer.nodes(canTransform ? [node] : []);
    if (canTransform) imageMergeState.transformer.moveToTop();
  }
  if (imageMergeDelete) {
    const name = node?.name?.() || "";
    imageMergeDelete.disabled = !node || name.startsWith("merge-panel-");
  }
  const name = node?.name?.() || "";
  const isText = name.startsWith("merge-text-") || name.startsWith("merge-label-");
  if (imageMergeTextInput) {
    imageMergeTextInput.disabled = !isText;
    imageMergeTextInput.value = isText && typeof node.text === "function" ? node.text() : "";
  }
  if (imageMergeFontSize && node && typeof node.fontSize === "function") {
    imageMergeFontSize.value = String(node.fontSize());
  }
  const rel = getSelectedPanelRel();
  const customMode = imageMergeLabels?.value === "custom";
  const customRow = document.getElementById("imageMergeCustomLabelRow");
  if (customRow) customRow.classList.toggle("hidden", !customMode);
  if (imageMergeCustomLabel) {
    imageMergeCustomLabel.disabled = !customMode || !rel;
    if (rel && customMode) {
      const panels =
        imageMergeState.layer?.find((n) => String(n.name?.() || "").startsWith("merge-panel-")) || [];
      const index = panels.findIndex((panel) => {
        const panelRel = panel.getAttr("panelRel") || panel.name().replace("merge-panel-", "");
        return panelRel === rel;
      });
      const defaultText = mergePanelLabel(Math.max(0, index), "upper");
      imageMergeCustomLabel.value = imageMergeState.customLabels[rel] || defaultText;
    } else {
      imageMergeCustomLabel.value = "";
    }
  }
  imageMergeState.layer?.batchDraw();
}

function getMergeNodeBounds(node) {
  const rect = node.getClientRect({ skipTransform: false });
  return {
    left: rect.x,
    top: rect.y,
    right: rect.x + rect.width,
    bottom: rect.y + rect.height,
    centerX: rect.x + rect.width / 2,
    centerY: rect.y + rect.height / 2,
  };
}

function clearMergeSnapGuides() {
  const guides = imageMergeState.layer?.findOne((node) => node.name() === "merge-snap-guides");
  if (guides) guides.destroy();
}

function showMergeSnapGuides(verticalX, horizontalY) {
  clearMergeSnapGuides();
  const layer = imageMergeState.layer;
  if (!layer) return;
  const w = imageMergeState.canvasW || imageMergeState.stage?.width() || 800;
  const h = imageMergeState.canvasH || imageMergeState.stage?.height() || 600;
  const group = new Konva.Group({ name: "merge-snap-guides", listening: false });
  if (verticalX != null) {
    group.add(
      new Konva.Line({
        points: [verticalX, 0, verticalX, h],
        stroke: "#f43f5e",
        strokeWidth: 1,
        dash: [6, 4],
        listening: false,
      })
    );
  }
  if (horizontalY != null) {
    group.add(
      new Konva.Line({
        points: [0, horizontalY, w, horizontalY],
        stroke: "#f43f5e",
        strokeWidth: 1,
        dash: [6, 4],
        listening: false,
      })
    );
  }
  if (group.children.length) {
    layer.add(group);
    group.moveToTop();
    imageMergeState.transformer?.moveToTop();
  }
}

function collectMergeSnapLines(excludeNode) {
  const vertical = new Set([0, (imageMergeState.canvasW || 0) / 2, imageMergeState.canvasW || 0]);
  const horizontal = new Set([0, (imageMergeState.canvasH || 0) / 2, imageMergeState.canvasH || 0]);
  const nodes =
    imageMergeState.layer?.find((node) => {
      const name = node.name?.() || "";
      return (
        name.startsWith("merge-panel-") ||
        name.startsWith("merge-label-") ||
        name.startsWith("merge-text-")
      );
    }) || [];
  nodes.forEach((node) => {
    if (node === excludeNode) return;
    const b = getMergeNodeBounds(node);
    vertical.add(b.left, b.centerX, b.right);
    horizontal.add(b.top, b.centerY, b.bottom);
  });
  return {
    vertical: [...vertical].filter((v) => Number.isFinite(v)),
    horizontal: [...horizontal].filter((v) => Number.isFinite(v)),
  };
}

function applyMergeSnap(node) {
  const bounds = getMergeNodeBounds(node);
  const lines = collectMergeSnapLines(node);
  const verticalRefs = [
    { edge: bounds.left, offset: 0 },
    { edge: bounds.centerX, offset: bounds.centerX - bounds.left },
    { edge: bounds.right, offset: bounds.right - bounds.left },
  ];
  const horizontalRefs = [
    { edge: bounds.top, offset: 0 },
    { edge: bounds.centerY, offset: bounds.centerY - bounds.top },
    { edge: bounds.bottom, offset: bounds.bottom - bounds.top },
  ];

  let bestDx = null;
  let bestDy = null;
  let guideX = null;
  let guideY = null;

  lines.vertical.forEach((line) => {
    verticalRefs.forEach(({ edge, offset }) => {
      const delta = line - edge;
      if (Math.abs(delta) <= MERGE_SNAP_THRESHOLD && (bestDx === null || Math.abs(delta) < Math.abs(bestDx))) {
        bestDx = delta;
        guideX = line;
      }
    });
  });
  lines.horizontal.forEach((line) => {
    horizontalRefs.forEach(({ edge, offset }) => {
      const delta = line - edge;
      if (Math.abs(delta) <= MERGE_SNAP_THRESHOLD && (bestDy === null || Math.abs(delta) < Math.abs(bestDy))) {
        bestDy = delta;
        guideY = line;
      }
    });
  });

  const pos = node.position();
  if (bestDx !== null) node.x(pos.x + bestDx);
  if (bestDy !== null) node.y(pos.y + bestDy);
  if (bestDx !== null || bestDy !== null) {
    showMergeSnapGuides(guideX, guideY);
  } else {
    clearMergeSnapGuides();
  }
}

function syncMergeLabelToPanel(node) {
  const name = node.name?.() || "";
  if (!name.startsWith("merge-panel-")) return;
  const rel = node.getAttr("panelRel") || name.replace("merge-panel-", "");
  const label = findMergeLabelNode(rel);
  if (!label) return;
  const fontSize = label.fontSize?.() || 28;
  label.position({ x: node.x() + 6, y: node.y() - fontSize - 6 });
}

function bindMergeNode(node) {
  node.on("click tap", (event) => {
    event.cancelBubble = true;
    setSelectedMergeNode(node);
  });
  node.on("dragstart", () => {
    setSelectedMergeNode(node);
    const pos = node.position();
    imageMergeState.mergeDragStart = { x: pos.x, y: pos.y };
    imageMergeState.mergeDragAxis = null;
    clearMergeSnapGuides();
  });
  node.on("dragmove", (event) => {
    const evt = event.evt;
    const start = imageMergeState.mergeDragStart;
    if (evt?.shiftKey && start) {
      if (!imageMergeState.mergeDragAxis) {
        const dx = Math.abs(node.x() - start.x);
        const dy = Math.abs(node.y() - start.y);
        if (dx > 2 || dy > 2) {
          imageMergeState.mergeDragAxis = dx >= dy ? "y" : "x";
        }
      }
      if (imageMergeState.mergeDragAxis === "x") node.x(start.x);
      else if (imageMergeState.mergeDragAxis === "y") node.y(start.y);
    } else if (!evt?.ctrlKey && !evt?.metaKey) {
      imageMergeState.mergeDragAxis = null;
    }

    if (evt?.ctrlKey || evt?.metaKey) {
      applyMergeSnap(node);
    } else {
      clearMergeSnapGuides();
    }
    syncMergeLabelToPanel(node);
  });
  node.on("dragend", () => {
    imageMergeState.mergeDragStart = null;
    imageMergeState.mergeDragAxis = null;
    clearMergeSnapGuides();
    fitMergeCanvasToContent(24);
    commitMergeState();
  });
  return node;
}

function updateMergeCustomLabelRow() {
  const custom = imageMergeLabels?.value === "custom";
  const rel = getSelectedPanelRel();
  const row = document.getElementById("imageMergeCustomLabelRow");
  row?.classList.toggle("hidden", !custom);
  if (imageMergeCustomLabel) imageMergeCustomLabel.disabled = !custom || !rel;
}

function findMergeLabelNode(rel) {
  return imageMergeState.layer?.findOne((node) => node.name() === `merge-label-${rel}`);
}

function syncMergePanelLabels() {
  const mode = imageMergeLabels?.value || "upper";
  const fontSize = Number(imageMergeLabelFontSize?.value || 28);
  const panels = imageMergeState.layer?.find((node) =>
    String(node.name?.() || "").startsWith("merge-panel-")
  ) || [];
  panels.forEach((panel, index) => {
    const rel = panel.getAttr("panelRel") || panel.name().replace("merge-panel-", "");
    let label = findMergeLabelNode(rel);
    const text = mergeLabelText(index, rel, mode);
    if (mode !== "none" && text && !label) {
      label = new Konva.Text({
        x: panel.x() + 6,
        y: panel.y() - fontSize - 6,
        text,
        fontSize,
        fontStyle: "bold",
        fontFamily: "Arial",
        fill: "#111827",
        draggable: true,
        name: `merge-label-${rel}`,
        panelRel: rel,
      });
      imageMergeState.layer.add(bindMergeNode(label));
    }
    if (label) {
      label.text(text);
      label.fontSize(fontSize);
      label.visible(mode !== "none" && Boolean(text));
      label.position({ x: panel.x() + 6, y: panel.y() - fontSize - 6 });
    }
  });
  imageMergeState.layer?.batchDraw();
}

function ensureMergeStage(w, h) {
  if (!window.Konva || !imageMergeStage) throw new Error(t("image.editorUnavailable"));
  destroyMergeStage();
  imageMergeState.canvasW = w;
  imageMergeState.canvasH = h;
  fitMergeStageDisplay(w, h);
  const stage = new Konva.Stage({
    container: imageMergeStage,
    width: w,
    height: h,
  });
  const layer = new Konva.Layer();
  const bgColor = MERGE_CANVAS_BG;
  const bg = new Konva.Rect({
    x: 0,
    y: 0,
    width: w,
    height: h,
    fill: bgColor,
    listening: false,
    name: "merge-bg",
  });
  const transformer = new Konva.Transformer({
    rotateEnabled: true,
    enabledAnchors: ["top-left", "top-right", "bottom-left", "bottom-right"],
    keepRatio: true,
    boundBoxFunc: (oldBox, newBox) => {
      if (newBox.width < 20 || newBox.height < 20) return oldBox;
      return newBox;
    },
  });
  layer.add(bg);
  layer.add(transformer);
  transformer.on("transformend", () => {
    fitMergeCanvasToContent(24);
    commitMergeState();
  });
  stage.add(layer);
  stage.on("click tap", (event) => {
    if (event.target === stage) setSelectedMergeNode(null);
  });
  imageMergeState.stage = stage;
  imageMergeState.layer = layer;
  imageMergeState.transformer = transformer;
  if (imageMergeStage) imageMergeStage.style.backgroundColor = bgColor;
  applyMergeViewZoom();
  updateMergeCanvasSizeLabel();
  return { stage, layer, transformer };
}

async function buildMergeAutoLayout(statusKey = "image.mergeLayoutReady") {
  if (!currentSessionId) return;
  const cfg = captureMergeConfig();
  if (cfg.selected.length < 1) {
    ensureMergeStage(800, 600);
    resetMergeHistory();
    commitMergeState();
    if (imageMergeStatus) imageMergeStatus.textContent = t("image.mergeSelectHint");
    return;
  }
  const gap = MERGE_LAYOUT_GAP;
  const labelMode = cfg.labels;
  const labelFontSize = Number(imageMergeLabelFontSize?.value || 28);
  const labelPad = labelMode === "none" ? 0 : labelFontSize + 10;
  const cols =
    cfg.cols === "auto"
      ? Math.max(1, Math.ceil(Math.sqrt(cfg.selected.length)))
      : Math.max(1, Number(cfg.cols) || 2);

  const images = await Promise.all(
    cfg.selected.map(async (rel, index) => {
      const url = workspaceFileUrl(currentSessionId, rel);
      const img = await loadImageElement(`${url}${url.includes("?") ? "&" : "?"}merge=${Date.now()}`);
      const iw = img.naturalWidth || img.width || 1;
      const ih = img.naturalHeight || img.height || 1;
      return { rel, img, index, w: iw, h: ih, scale: 1 };
    })
  );

  const cellW = Math.max(...images.map((item) => item.w), 120);
  const cellH = Math.max(...images.map((item) => item.h), 80);
  const rows = Math.ceil(images.length / cols);
  const placements = images.map(({ w, h }, index) => {
    const col = index % cols;
    const row = Math.floor(index / cols);
    const x = gap + col * (cellW + gap) + Math.round((cellW - w) / 2);
    const y = gap + labelPad + row * (cellH + labelPad + gap);
    return { x, y, w, h };
  });
  const rightEdge = Math.max(...placements.map((p) => p.x + p.w), 0) + gap;
  const bottomEdge = Math.max(...placements.map((p) => p.y + p.h), 0) + gap;
  const canvasW = Math.max(rightEdge, 200);
  const canvasH = Math.max(bottomEdge, 150);

  const { layer } = ensureMergeStage(canvasW, canvasH);

  images.forEach(({ rel, img, index, w, h, scale }, i) => {
    const { x, y } = placements[i];
    const panel = new Konva.Image({
      x,
      y,
      image: img,
      width: img.naturalWidth || img.width,
      height: img.naturalHeight || img.height,
      scaleX: scale,
      scaleY: scale,
      draggable: true,
      name: `merge-panel-${rel}`,
      panelRel: rel,
    });
    layer.add(bindMergeNode(panel));

    const labelText = mergeLabelText(index, rel, labelMode);
    if (labelMode !== "none" && labelText) {
      const label = new Konva.Text({
        x: x + 6,
        y: y - labelFontSize - 6,
        text: labelText,
        fontSize: labelFontSize,
        fontStyle: "bold",
        fontFamily: "Arial",
        fill: "#111827",
        draggable: true,
        name: `merge-label-${rel}`,
        panelRel: rel,
      });
      layer.add(bindMergeNode(label));
    }
  });

  fitMergeCanvasToContent(32);
  layer.batchDraw();
  commitMergeState();
  fitMergeViewToPanel();
  if (imageMergeStatus && statusKey) imageMergeStatus.textContent = t(statusKey);
}

async function restoreMergeNodes(cfg) {
  if (!cfg?.nodes?.length) {
    return buildMergeAutoLayout();
  }
  const { layer } = ensureMergeStage(cfg.canvasW || 1200, cfg.canvasH || 900);
  const bg = layer.findOne((node) => node.name() === "merge-bg");
  if (bg) bg.fill(MERGE_CANVAS_BG);

  for (const item of cfg.nodes) {
    if (item.type === "panel") {
      const url = workspaceFileUrl(currentSessionId, item.rel);
      const img = await loadImageElement(`${url}${url.includes("?") ? "&" : "?"}merge=${Date.now()}`);
      const panel = new Konva.Image({
        x: item.x,
        y: item.y,
        image: img,
        width: img.naturalWidth || img.width,
        height: img.naturalHeight || img.height,
        scaleX: item.scaleX ?? 1,
        scaleY: item.scaleY ?? 1,
        rotation: item.rotation || 0,
        draggable: true,
        name: `merge-panel-${item.rel}`,
        panelRel: item.rel,
      });
      layer.add(bindMergeNode(panel));
    } else if (item.type === "label") {
      const label = new Konva.Text({
        x: item.x,
        y: item.y,
        text: item.text || "",
        fontSize: item.fontSize || 28,
        fontStyle: "bold",
        fontFamily: "Arial",
        fill: item.fill || "#111827",
        rotation: item.rotation || 0,
        draggable: true,
        name: `merge-label-${item.rel}`,
        panelRel: item.rel,
      });
      layer.add(bindMergeNode(label));
    } else if (item.type === "text") {
      const textNode = new Konva.Text({
        x: item.x,
        y: item.y,
        text: item.text || t("image.newText"),
        fontSize: item.fontSize || 24,
        fontFamily: "Arial",
        fill: item.fill || "#111827",
        rotation: item.rotation || 0,
        draggable: true,
        name: item.name || `merge-text-${Date.now()}`,
      });
      layer.add(bindMergeNode(textNode));
    }
  }
  fitMergeCanvasToContent(32);
  layer.batchDraw();
  fitMergeViewToPanel();
}

function addMergeFreeText() {
  if (!imageMergeState.layer) return;
  imageMergeState.freeTextCount += 1;
  const node = new Konva.Text({
    x: 48,
    y: 48 + imageMergeState.freeTextCount * 36,
    text: t("image.newText"),
    fontSize: Number(imageMergeFontSize?.value || 24),
    fontFamily: "Arial",
    fill: "#111827",
    draggable: true,
    name: `merge-text-${Date.now()}`,
  });
  imageMergeState.layer.add(bindMergeNode(node));
  setSelectedMergeNode(node);
  if (imageMergeTextInput) imageMergeTextInput.value = node.text();
  if (imageMergeStatus) imageMergeStatus.textContent = t("image.mergeTextAdded");
  commitMergeState();
}

function renderImageMergePickList() {
  if (!imageMergePickList) return;
  imageMergePickList.innerHTML = "";
  if (!workspaceOutputImages.length) {
    const empty = document.createElement("p");
    empty.className = "image-merge-pick-empty muted";
    empty.textContent = t("image.mergeNoImages");
    imageMergePickList.appendChild(empty);
    return;
  }
  workspaceOutputImages.forEach((file) => {
    const url = workspaceFileUrl(currentSessionId, file.name);
    if (!url) return;
    const card = document.createElement("button");
    card.type = "button";
    card.className = "image-merge-pick-card";
    if (imageMergeState.selected.includes(file.name)) {
      card.classList.add("selected");
    }
    card.title = file.name;

    const thumb = document.createElement("span");
    thumb.className = "image-merge-pick-thumb";
    const img = document.createElement("img");
    img.loading = "lazy";
    img.alt = "";
    img.src = url;
    thumb.appendChild(img);

    const title = document.createElement("span");
    title.className = "image-merge-pick-title";
    title.textContent = file.name.split("/").pop();

    card.appendChild(thumb);
    card.appendChild(title);
    card.addEventListener("click", () => toggleMergeImageSelection(file.name));
    imageMergePickList.appendChild(card);
  });
}

function toggleMergeImageSelection(rel) {
  if (imageMergeState.layer) commitMergeState();
  const index = imageMergeState.selected.indexOf(rel);
  if (index >= 0) {
    imageMergeState.selected.splice(index, 1);
  } else {
    imageMergeState.selected.push(rel);
  }
  renderImageMergePickList();
  buildMergeAutoLayout("image.mergeImageToggled").catch((err) => {
    if (imageMergeStatus) imageMergeStatus.textContent = err.message;
  });
}

function openImageMergeEditor() {
  if (!imageMergeEditor || !currentSessionId || isSharedView) return;
  if (!window.Konva) {
    setStatus(t("image.editorUnavailable"));
    return;
  }
  closeImageLightbox();
  closeImageEditor();
  closePlotlyEditor();
  resetMergeHistory();
  destroyMergeStage();
  imageMergeState.selected = [];
  imageMergeState.customLabels = {};
  imageMergeState.freeTextCount = 0;
  imageMergeState.viewZoom = 1;
  renderImageMergePickList();
  updateMergeCustomLabelRow();
  if (imageMergeUndo) imageMergeUndo.disabled = true;
  if (imageMergeStatus) imageMergeStatus.textContent = t("image.mergeSelectHint");
  imageMergeEditor.classList.remove("hidden");
  imageMergeEditor.setAttribute("aria-hidden", "false");
  buildMergeAutoLayout().catch((err) => {
    if (imageMergeStatus) imageMergeStatus.textContent = err.message;
  });
}

function closeImageMergeEditor() {
  if (!imageMergeEditor) return;
  imageMergeEditor.classList.add("hidden");
  imageMergeEditor.setAttribute("aria-hidden", "true");
  destroyMergeStage();
  resetMergeHistory();
}

async function saveImageMerge() {
  if (!currentSessionId || !imageMergeState.stage) return;
  const cfg = captureMergeConfig();
  if (cfg.selected.length < 1) {
    if (imageMergeStatus) imageMergeStatus.textContent = t("image.mergeNeedOne");
    return;
  }
  try {
    if (imageMergeStatus) imageMergeStatus.textContent = t("image.mergeSaving");
    if (imageMergeSave) imageMergeSave.disabled = true;
    setSelectedMergeNode(null);
    const imageData = exportMergeStagePng();
    const sourceRel = cfg.selected[0];
    const res = await fetch(`/api/sessions/${currentSessionId}/image-edits`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_rel: sourceRel,
        image_data: imageData,
        edit_state: {
          version: 2,
          type: "merged_figure",
          ...cfg,
        },
        filename: "merged_figure.png",
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || t("image.saveFail"));
    closeImageMergeEditor();
    await loadWorkspaceFiles(currentSessionId);
    setStatus(t("image.saved", { name: data.file?.name || "merged_figure.png" }));
  } catch (err) {
    if (imageMergeStatus) imageMergeStatus.textContent = t("image.saveFailWithMsg", { msg: err.message });
  } finally {
    if (imageMergeSave) imageMergeSave.disabled = false;
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

/** 与 web_frontend/backend/agent_intent.py 语义一致：分析/改图/拼图均走统一 Agent */
function shouldUseAgent(message, hasNewUpload = false) {
  const text = (message || "").trim();
  if (!text) return false;
  if (shouldUsePlotEdit(text)) return true;
  if (shouldUseImageMerge(text)) return true;
  if (shouldUseMergeFigureEdit(text)) return true;
  if (hasNewUpload) return true;
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
          if (payload?.visual_results?.length) {
            statusText.className = "status-text status-ok";
            setStatus(t("status.visualDone"));
          } else if (payload?.plot_edit) {
            statusText.className = "status-text status-ok";
            setStatus(t("status.plotEditDone"));
          } else if (payload?.image_merge) {
            statusText.className = "status-text status-ok";
            setStatus(t("status.imageMergeDone"));
          } else {
            const tail = "\n\n---\n✅ **分析已完成**";
            if (!assistantText.includes("分析已完成")) {
              assistantText += tail;
              assistantEl.contentEl.textContent = assistantText;
            }
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
  syncChatColorPickerFromInput();
});

function normalizeHexColor(value) {
  const raw = String(value || "").trim();
  if (!raw) return "#4DBBD5";
  const withHash = raw.startsWith("#") ? raw : `#${raw}`;
  if (/^#[0-9a-fA-F]{3}$/.test(withHash)) {
    const r = withHash[1];
    const g = withHash[2];
    const b = withHash[3];
    return `#${r}${r}${g}${g}${b}${b}`.toUpperCase();
  }
  if (/^#[0-9a-fA-F]{6}$/.test(withHash)) return withHash.toUpperCase();
  return "#4DBBD5";
}

function insertTextAtCursor(textarea, text) {
  if (!textarea) return;
  const start = textarea.selectionStart ?? textarea.value.length;
  const end = textarea.selectionEnd ?? start;
  const before = textarea.value.slice(0, start);
  const after = textarea.value.slice(end);
  textarea.value = `${before}${text}${after}`;
  const pos = start + text.length;
  textarea.setSelectionRange(pos, pos);
  textarea.focus();
  textarea.dispatchEvent(new Event("input", { bubbles: true }));
}

function setChatColorSelection(hex) {
  const color = normalizeHexColor(hex);
  chatColorState.selected = color;
  if (chatColorNative) chatColorNative.value = color;
  if (chatColorHexPreview) chatColorHexPreview.textContent = color;
  if (chatColorBtnSwatch) chatColorBtnSwatch.style.background = color;
  if (chatColorPresets) {
    chatColorPresets.querySelectorAll(".chat-color-preset").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.color?.toUpperCase() === color);
    });
  }
}

function renderChatColorPresets() {
  if (!chatColorPresets) return;
  chatColorPresets.innerHTML = "";
  CHAT_COLOR_PRESETS.forEach((hex) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chat-color-preset";
    btn.dataset.color = hex.toUpperCase();
    btn.style.background = hex;
    btn.title = hex;
    btn.addEventListener("click", () => setChatColorSelection(hex));
    chatColorPresets.appendChild(btn);
  });
}

function openChatColorPicker({ replaceHash = false, hashIndex = -1 } = {}) {
  if (!chatColorPopover) return;
  chatColorState.open = true;
  chatColorState.replaceHash = replaceHash;
  chatColorState.hashIndex = hashIndex;
  chatColorPopover.classList.remove("hidden");
  chatColorPopover.setAttribute("aria-hidden", "false");
  setChatColorSelection(chatColorState.selected);
}

function closeChatColorPicker() {
  if (!chatColorPopover) return;
  chatColorState.open = false;
  chatColorState.replaceHash = false;
  chatColorState.hashIndex = -1;
  chatColorPopover.classList.add("hidden");
  chatColorPopover.setAttribute("aria-hidden", "true");
}

function applyChatColorSelection() {
  const color = normalizeHexColor(chatColorState.selected);
  if (!promptInput) {
    closeChatColorPicker();
    return;
  }
  if (chatColorState.replaceHash && chatColorState.hashIndex >= 0) {
    const value = promptInput.value;
    const index = chatColorState.hashIndex;
    if (value[index] === "#") {
      promptInput.value = `${value.slice(0, index)}${color}${value.slice(index + 1)}`;
      const pos = index + color.length;
      promptInput.setSelectionRange(pos, pos);
      promptInput.dispatchEvent(new Event("input", { bubbles: true }));
    } else {
      insertTextAtCursor(promptInput, color);
    }
  } else {
    insertTextAtCursor(promptInput, color);
  }
  closeChatColorPicker();
}

function syncChatColorPickerFromInput() {
  if (!promptInput || chatColorState.open) return;
  const value = promptInput.value;
  const cursor = promptInput.selectionStart ?? value.length;
  const tail = value.slice(0, cursor);
  const match = tail.match(/#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/);
  if (match) {
    setChatColorSelection(`#${match[1]}`);
  }
}

promptInput.addEventListener("keydown", (event) => {
  if (event.key === "#" && !event.ctrlKey && !event.metaKey && !event.altKey) {
    chatColorState.pendingHash = true;
    chatColorState.pendingHashIndex = promptInput.selectionStart;
  }
  if (event.key === "Escape" && chatColorState.open) {
    event.preventDefault();
    closeChatColorPicker();
    return;
  }
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

promptInput.addEventListener("keyup", () => {
  if (!chatColorState.pendingHash) return;
  chatColorState.pendingHash = false;
  const index = chatColorState.pendingHashIndex ?? -1;
  if (index >= 0 && promptInput.value[index] === "#") {
    openChatColorPicker({ replaceHash: true, hashIndex: index });
  }
});

if (chatColorBtn) {
  chatColorBtn.addEventListener("click", () => {
    if (chatColorState.open) {
      closeChatColorPicker();
      return;
    }
    openChatColorPicker({ replaceHash: false });
  });
}
if (chatColorNative) {
  chatColorNative.addEventListener("input", () => setChatColorSelection(chatColorNative.value));
}
if (chatColorConfirm) chatColorConfirm.addEventListener("click", applyChatColorSelection);
if (chatColorCancel) {
  chatColorCancel.addEventListener("click", () => closeChatColorPicker());
}
if (chatColorClose) {
  chatColorClose.addEventListener("click", () => closeChatColorPicker());
}
renderChatColorPresets();
setChatColorSelection(chatColorState.selected);

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
    commitKonvaState();
  });
}
let konvaOverlayDirty = false;
function markKonvaOverlayDirty() {
  konvaOverlayDirty = true;
}
function commitKonvaOverlayIfDirty() {
  if (!konvaOverlayDirty) return;
  commitKonvaState();
  konvaOverlayDirty = false;
}
if (editorTextInput) {
  editorTextInput.addEventListener("input", () => {
    const node = imageEditorState.selectedNode;
    if (node && typeof node.text === "function") {
      node.text(editorTextInput.value);
      imageEditorState.layer?.batchDraw();
      markKonvaOverlayDirty();
    }
  });
  editorTextInput.addEventListener("blur", commitKonvaOverlayIfDirty);
}
if (editorColorInput) {
  editorColorInput.addEventListener("input", () => {
    const node = imageEditorState.selectedNode;
    if (!node) return;
    if (typeof node.fill === "function") node.fill(editorColorInput.value);
    if (typeof node.stroke === "function") node.stroke(editorColorInput.value);
    imageEditorState.layer?.batchDraw();
    markKonvaOverlayDirty();
  });
  editorColorInput.addEventListener("blur", commitKonvaOverlayIfDirty);
}
if (editorRasterTolerance) {
  editorRasterTolerance.addEventListener("input", () => {
    if (editorRasterToleranceVal) editorRasterToleranceVal.textContent = editorRasterTolerance.value;
  });
}
if (editorEyedropper) {
  editorEyedropper.addEventListener("click", () => {
    setEyedropperActive(!imageEditorState.eyedropperActive);
    if (imageEditorState.eyedropperActive) {
      setEditorStatus(t("image.eyedropperActive"));
    }
  });
}
if (editorReplaceAllColors) {
  editorReplaceAllColors.addEventListener("click", () => {
    if (!imageEditorState.pickedRasterColor) {
      setEditorStatus(t("image.rasterPickFirst"), "error");
      return;
    }
    replaceRasterColor(
      imageEditorState.pickedRasterColor,
      editorRasterTargetColor?.value || "#2563eb"
    );
  });
}
if (editorUndo) {
  editorUndo.addEventListener("click", undoKonvaEdit);
}
if (editorFontSizeInput) {
  editorFontSizeInput.addEventListener("input", () => {
    const node = imageEditorState.selectedNode;
    if (node && typeof node.fontSize === "function") {
      node.fontSize(Number(editorFontSizeInput.value || 24));
      imageEditorState.layer?.batchDraw();
      markKonvaOverlayDirty();
    }
  });
  editorFontSizeInput.addEventListener("blur", commitKonvaOverlayIfDirty);
}
function rebuildMergeLayoutWithFeedback(statusKey = "image.mergeLayoutReady") {
  if (imageMergeState.selected.length < 1) {
    if (imageMergeStatus) imageMergeStatus.textContent = t("image.mergeSelectHint");
    return Promise.resolve();
  }
  return buildMergeAutoLayout(statusKey);
}

function bindMergeConfigUndo() {
  const commitBefore = () => commitMergeState();
  imageMergeCols?.addEventListener("focus", commitBefore);
  imageMergeLabels?.addEventListener("focus", commitBefore);
  imageMergeLabelFontSize?.addEventListener("focus", commitBefore);
}
bindMergeConfigUndo();
if (openImageMergeBtn) {
  openImageMergeBtn.addEventListener("click", openImageMergeEditor);
}
if (imageMergeZoomOut) {
  imageMergeZoomOut.addEventListener("click", () => {
    setMergeViewZoom((imageMergeState.viewZoom || 1) / 1.15);
  });
}
if (imageMergeZoomIn) {
  imageMergeZoomIn.addEventListener("click", () => {
    setMergeViewZoom((imageMergeState.viewZoom || 1) * 1.15);
  });
}
if (imageMergeZoomFit) {
  imageMergeZoomFit.addEventListener("click", () => {
    fitMergeViewToPanel();
    if (imageMergeStatus) {
      imageMergeStatus.textContent = t("image.mergeZoomApplied", {
        pct: Math.round((imageMergeState.viewZoom || 1) * 100),
      });
    }
  });
}
if (imageMergePreviewWrap) {
  imageMergePreviewWrap.addEventListener(
    "wheel",
    (event) => {
      if (!imageMergeEditor || imageMergeEditor.classList.contains("hidden")) return;
      if (!event.altKey) return;
      event.preventDefault();
      const factor = event.deltaY > 0 ? 0.9 : 1.1;
      setMergeViewZoom((imageMergeState.viewZoom || 1) * factor);
    },
    { passive: false }
  );
}
if (imageMergeAutoLayout) {
  imageMergeAutoLayout.addEventListener("click", () => {
    commitMergeState();
    rebuildMergeLayoutWithFeedback("image.mergeLayoutReady").catch((err) => {
      if (imageMergeStatus) imageMergeStatus.textContent = err.message;
    });
  });
}
if (imageMergeCols) {
  imageMergeCols.addEventListener("change", () => {
    rebuildMergeLayoutWithFeedback("image.mergeColsApplied").catch((err) => {
      if (imageMergeStatus) imageMergeStatus.textContent = err.message;
    });
  });
}
if (imageMergeLabels) {
  imageMergeLabels.addEventListener("change", () => {
    updateMergeCustomLabelRow();
    syncMergePanelLabels();
    if (imageMergeStatus) imageMergeStatus.textContent = t("image.mergeLabelsApplied");
    commitMergeState();
  });
}
if (imageMergeLabelFontSize) {
  imageMergeLabelFontSize.addEventListener("input", () => {
    syncMergePanelLabels();
    if (imageMergeStatus) imageMergeStatus.textContent = t("image.mergeLabelSizeApplied");
  });
  imageMergeLabelFontSize.addEventListener("change", () => commitMergeState());
}
if (imageMergeCustomLabel) {
  imageMergeCustomLabel.addEventListener("input", () => {
    const rel = getSelectedPanelRel();
    if (!rel) return;
    imageMergeState.customLabels[rel] = imageMergeCustomLabel.value;
    const label = findMergeLabelNode(rel);
    if (label) {
      label.text(imageMergeCustomLabel.value);
      label.visible(Boolean(imageMergeCustomLabel.value));
      imageMergeState.layer?.batchDraw();
      if (imageMergeStatus) imageMergeStatus.textContent = t("image.mergeCustomLabelApplied");
    }
  });
  imageMergeCustomLabel.addEventListener("change", () => commitMergeState());
}
if (imageMergeAddText) {
  imageMergeAddText.addEventListener("click", addMergeFreeText);
}
if (imageMergeTextInput) {
  imageMergeTextInput.addEventListener("input", () => {
    const node = imageMergeState.selectedNode;
    if (node && typeof node.text === "function") {
      node.text(imageMergeTextInput.value);
      imageMergeState.layer?.batchDraw();
      if (imageMergeStatus) imageMergeStatus.textContent = t("image.mergeTextApplied");
    }
  });
  imageMergeTextInput.addEventListener("change", () => commitMergeState());
}
if (imageMergeFontSize) {
  imageMergeFontSize.addEventListener("input", () => {
    const node = imageMergeState.selectedNode;
    if (node && typeof node.fontSize === "function") {
      node.fontSize(Number(imageMergeFontSize.value || 24));
      imageMergeState.layer?.batchDraw();
      if (imageMergeStatus) imageMergeStatus.textContent = t("image.mergeTextSizeApplied");
    }
  });
  imageMergeFontSize.addEventListener("change", () => commitMergeState());
}
if (imageMergeDelete) {
  imageMergeDelete.addEventListener("click", () => {
    const node = imageMergeState.selectedNode;
    if (!node) return;
    const name = node.name?.() || "";
    if (name.startsWith("merge-panel-")) return;
    node.destroy();
    setSelectedMergeNode(null);
    if (imageMergeStatus) imageMergeStatus.textContent = t("image.mergeDeleted");
    commitMergeState();
  });
}
if (editorTitlePosition) {
  editorTitlePosition.addEventListener("change", () => {
    applyTitlePosition(editorTitlePosition.value);
    commitKonvaState();
  });
}
if (editorSave) editorSave.addEventListener("click", saveImageEdit);
if (editorCancel) editorCancel.addEventListener("click", closeImageEditor);
if (editorClose) editorClose.addEventListener("click", closeImageEditor);
if (editorBackdrop) editorBackdrop.addEventListener("click", closeImageEditor);
if (imageMergeUndo) {
  imageMergeUndo.addEventListener("click", undoMergeEdit);
}
if (imageMergeSave) {
  imageMergeSave.addEventListener("click", saveImageMerge);
}
if (imageMergeCancel) {
  imageMergeCancel.addEventListener("click", closeImageMergeEditor);
}
if (imageMergeClose) {
  imageMergeClose.addEventListener("click", closeImageMergeEditor);
}
if (imageMergeBackdrop) {
  imageMergeBackdrop.addEventListener("click", closeImageMergeEditor);
}
if (plotlyLegendColorInput) {
  plotlyLegendColorInput.addEventListener("change", () => {
    applyPlotlyTraceColor(plotlyEditorState.selectedTrace, plotlyLegendColorInput.value);
  });
}
let plotlyFontEditTimer = null;
function schedulePlotlyFontApply() {
  if (plotlyFontEditTimer) clearTimeout(plotlyFontEditTimer);
  plotlyFontEditTimer = setTimeout(() => {
    plotlyFontEditTimer = null;
    applyPlotlyFontSizes({
      titleSize: Number(plotlyTitleFontSizeInput?.value || 18),
      axisSize: Number(plotlyAxisFontSizeInput?.value || 14),
    });
  }, 280);
}
if (plotlyTitleFontSizeInput) {
  plotlyTitleFontSizeInput.addEventListener("input", schedulePlotlyFontApply);
}
if (plotlyAxisFontSizeInput) {
  plotlyAxisFontSizeInput.addEventListener("input", schedulePlotlyFontApply);
}
if (plotlyTraceSelect) {
  plotlyTraceSelect.addEventListener("change", () => {
    if (!plotlyTraceSelect.value) return;
    selectPlotlyTrace(Number(plotlyTraceSelect.value), { openPicker: false });
  });
}
if (plotlyEditorUndo) {
  plotlyEditorUndo.addEventListener("click", undoPlotlyEdit);
}
if (plotlyEditorSave) plotlyEditorSave.addEventListener("click", savePlotlyEdit);
if (plotlyEditorCancel) plotlyEditorCancel.addEventListener("click", closePlotlyEditor);
if (plotlyEditorClose) plotlyEditorClose.addEventListener("click", closePlotlyEditor);
if (plotlyEditorBackdrop) plotlyEditorBackdrop.addEventListener("click", closePlotlyEditor);
if (plotAgentEditorApply) plotAgentEditorApply.addEventListener("click", submitPlotAgentEdit);
if (plotAgentEditorCancel) plotAgentEditorCancel.addEventListener("click", closePlotAgentEditor);
if (plotAgentEditorClose) plotAgentEditorClose.addEventListener("click", closePlotAgentEditor);
if (plotAgentEditorBackdrop) plotAgentEditorBackdrop.addEventListener("click", closePlotAgentEditor);
if (mergeAgentEditorApply) mergeAgentEditorApply.addEventListener("click", submitMergeAgentEdit);
if (mergeAgentEditorCancel) mergeAgentEditorCancel.addEventListener("click", closeMergeAgentEditor);
if (mergeAgentEditorClose) mergeAgentEditorClose.addEventListener("click", closeMergeAgentEditor);
if (mergeAgentEditorBackdrop) mergeAgentEditorBackdrop.addEventListener("click", closeMergeAgentEditor);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && mergeAgentEditor && !mergeAgentEditor.classList.contains("hidden")) {
    closeMergeAgentEditor();
    return;
  }
  if (event.key === "Escape" && plotAgentEditor && !plotAgentEditor.classList.contains("hidden")) {
    closePlotAgentEditor();
    return;
  }
  if (event.key === "Escape" && imageMergeEditor && !imageMergeEditor.classList.contains("hidden")) {
    closeImageMergeEditor();
    return;
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
    if (imageEditor && !imageEditor.classList.contains("hidden")) {
      event.preventDefault();
      undoKonvaEdit();
      return;
    }
    if (plotlyEditor && !plotlyEditor.classList.contains("hidden")) {
      event.preventDefault();
      undoPlotlyEdit();
      return;
    }
    if (imageMergeEditor && !imageMergeEditor.classList.contains("hidden")) {
      event.preventDefault();
      undoMergeEdit();
      return;
    }
  }
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
