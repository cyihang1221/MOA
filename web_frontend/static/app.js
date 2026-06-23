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

    side.appendChild(title);
    side.appendChild(meta);
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
    useAgent: /\[已上传附件\]|\[Attachments uploaded\]/.test(content),
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

    const uploadMarker = /\[已上传附件\]|\[Attachments uploaded\]/;
    const agentIntent =
      /继续|重新运行|执行分析|跑一遍|开始分析|运行工具|continue|re-?run|run analysis|start agent|execute pipeline/i;
    const useAgent =
      uploaded.length > 0 ||
      uploadMarker.test(finalMessage) ||
      agentIntent.test(text);
    await runAssistantStream({ userMessage: finalMessage, useAgent });
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
document.addEventListener("keydown", (event) => {
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
