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
      <button type="button" aria-label="移除">×</button>
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
    setStatus("已终止（后续步骤已跳过；若终端仍在输出，属当前工具收尾）");
    return;
  }
  if (payload?.error) {
    statusText.className = "status-text status-error";
    setStatus(`完成（有错误）：${payload.error}`);
    return;
  }
  if (payload?.finished !== false) {
    statusText.className = "status-text status-ok";
    setStatus("✅ 分析已完成，结果已保存到会话目录");
    return;
  }
  statusText.className = "status-text";
  setStatus("完成");
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
    editBtn.textContent = "编辑";
    editBtn.addEventListener("click", () =>
      openMessageEditor(div, messageId, contentEl.textContent)
    );
    actionsEl.appendChild(editBtn);
  }

  const metaEl = document.createElement("div");
  metaEl.className = "message-meta";
  const label = role === "user" ? "你" : "MassAgent";
  metaEl.textContent = `${label} · ${displayTime(timeStr) || ""}`;

  div.appendChild(contentEl);
  if (actionsEl.childElementCount) div.appendChild(actionsEl);
  div.appendChild(metaEl);
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  if (role === "assistant" && messageId != null) {
    lastAssistantMessageId = messageId;
  }
  return { div, contentEl, metaEl, actionsEl };
}

function openMessageEditor(messageDiv, messageId, currentText) {
  if (isStreaming) {
    setStatus("请等待当前回复结束后再编辑");
    return;
  }
  const contentEl = messageDiv.querySelector(".message-content");
  const existing = messageDiv.querySelector(".message-editor-wrap");
  if (existing) return;

  const wrap = document.createElement("div");
  wrap.className = "message-editor-wrap";
  const editor = document.createElement("textarea");
  editor.className = "message-editor";
  editor.value = currentText || "";

  const btnRow = document.createElement("div");
  btnRow.className = "message-edit-actions";
  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "secondary-btn small-btn";
  cancelBtn.textContent = "取消";
  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  saveBtn.className = "small-btn";
  saveBtn.textContent = "保存并重发";

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
      setStatus(`失败：${err.message}`);
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
    useAgent: /\[已上传附件\]/.test(content),
  });
}

function renderToolsCatalog(categories, targetEl, compact = false) {
  targetEl.innerHTML = "";
  categories.forEach((group) => {
    const section = document.createElement("section");
    section.className = compact ? "tools-group compact" : "tools-group";
    const title = document.createElement("h3");
    title.textContent = group.category;
    section.appendChild(title);

    const list = document.createElement("div");
    list.className = "tools-grid";
    group.tools.forEach((tool) => {
      const card = document.createElement("article");
      card.className = "tool-card";
      card.innerHTML = `
        <div class="tool-name">${tool.name}</div>
        <div class="tool-desc">${tool.description || "暂无描述"}</div>
      `;
      list.appendChild(card);
    });
    section.appendChild(list);
    targetEl.appendChild(section);
  });
}

function normalizePath(path) {
  if (!path) return "";
  return String(path).replace(/\\/g, "/");
}

function renderRuntimeInfo(runtime) {
  if (!runtimeInfo) return;
  if (!runtime) {
    runtimeInfo.textContent = "运行环境信息不可用";
    return;
  }
  appRuntime = runtime;
  const lines = [];
  lines.push(`系统：${runtime.platform || "未知"}`);
  if (runtime.preferred_raw_converter?.tool) {
    lines.push(`RAW 转换：${runtime.preferred_raw_converter.tool}`);
  }
  lines.push(`R：${runtime.r_available ? "可用" : "未检测到"}`);
  lines.push(`Docker：${runtime.docker_available ? "可用" : "未检测到"}`);

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
    runtimeInfo.textContent = "运行环境检测失败（不影响聊天）";
  }
}

async function initTools() {
  try {
    const res = await fetch("/api/tools", { signal: fetchTimeoutSignal(60000) });
    const data = await res.json();
    toolsCount.textContent = data.total ? `(${data.total})` : "";
    renderToolsCatalog(data.categories || [], toolsPanel, false);
    renderToolsCatalog(data.categories || [], toolsSidebar, true);
  } catch {
    toolsPanel.innerHTML = "<p class='muted'>工具列表加载失败</p>";
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
    modelSelect.innerHTML = "<option value=''>模型加载失败</option>";
  }
}

async function fetchSessions() {
  const res = await fetch("/api/sessions");
  if (!res.ok) throw new Error("获取会话列表失败");
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
  if (!res.ok) throw new Error(data.detail || "创建会话失败");
  return data.session_id;
}

async function deleteSession(sessionId) {
  const res = await fetch(`/api/sessions/${sessionId}`, { method: "DELETE" });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "删除失败");
}

async function renameSession(sessionId, title) {
  const res = await fetch(`/api/sessions/${sessionId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "重命名失败");
}

async function enableShare(sessionId) {
  const res = await fetch(`/api/sessions/${sessionId}/share`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ shared: true }),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "开启分享失败");
}

async function uploadPendingFiles(sessionId) {
  if (pendingFiles.length === 0) return [];
  const formData = new FormData();
  pendingFiles.forEach((file) => formData.append("files", file, file.name));
  const res = await fetch(`/api/sessions/${sessionId}/files`, {
    method: "POST",
    body: formData,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "文件上传失败");
  pendingFiles = [];
  renderAttachments();
  return data.files || [];
}

function buildUserMessage(text, uploadedFiles) {
  const trimmed = (text || "").trim();
  if (!uploadedFiles.length) return trimmed;

  const fileLines = uploadedFiles
    .map((f) => `- ${f.name} (${formatSize(f.size)})\n  路径: ${normalizePath(f.path)}`)
    .join("\n");

  const base =
    trimmed ||
    "请根据已上传的文件选择合适的工具进行分析，并给出清晰的结果摘要。";

  return `${base}\n\n[已上传附件]\n${fileLines}\n\n请根据文件类型与我的需求，从可用工具中选择合适流程处理。`;
}

function renderSessionList() {
  sessionListEl.innerHTML = "";
  if (isSharedView) {
    const item = document.createElement("div");
    item.className = "session-item active";
    item.textContent = "分享会话（只读）";
    sessionListEl.appendChild(item);
    return;
  }

  sessions.forEach((session) => {
    const item = document.createElement("div");
    item.className = `session-item ${session.id === currentSessionId ? "active" : ""}`;
    const titleEl = document.createElement("div");
    titleEl.className = "session-title";
    titleEl.textContent = session.title || "未命名会话";
    if (session.is_shared) {
      const badge = document.createElement("span");
      badge.className = "share-badge";
      badge.textContent = "已分享";
      titleEl.appendChild(badge);
    }
    const actionsEl = document.createElement("div");
    actionsEl.className = "session-actions";
    const renameBtn = document.createElement("button");
    renameBtn.type = "button";
    renameBtn.className = "session-action-btn";
    renameBtn.textContent = "重命名";
    renameBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const newTitle = prompt("输入新的会话名称", session.title || "新会话");
      if (!newTitle) return;
      await renameSession(session.id, newTitle.trim());
      await fetchSessions();
      currentSessionId = session.id;
      renderSessionList();
      await loadMessages(currentSessionId);
    });
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "session-action-btn";
    deleteBtn.textContent = "删除";
    deleteBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      if (!confirm(`确定删除会话：${session.title || ""} ？`)) return;
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
      await loadMessages(currentSessionId);
    });
    sessionListEl.appendChild(item);
  });
}

function toggleWelcomePanel(show) {
  welcomePanel.classList.toggle("hidden", !show);
}

async function loadMessages(sessionId) {
  messagesEl.innerHTML = "";
  const res = await fetch(`/api/sessions/${sessionId}/messages`);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "加载消息失败");
  const msgs = data.messages || [];
  toggleWelcomePanel(msgs.length <= 1);
  lastAssistantMessageId = null;
  msgs.forEach((m) => createMessageEl(m.role, m.content, m.time || "", m.id));
}

async function loadSharedMessages(sessionId) {
  messagesEl.innerHTML = "";
  const res = await fetch(`/api/public/sessions/${sessionId}/messages`);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "分享会话不存在或未开启分享");
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
  await loadMessages(currentSessionId);
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
    throw new Error(
      "网络连接失败（请确认服务已启动；上传附件后 Agent 可能需数分钟，勿关闭页面）"
    );
  }
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(detail || `请求失败 (${res.status})`);
  }
  try {
    await consumeSseStream(res, onDelta, onDone, onError, signal);
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new Error(
      "连接中断（Agent 执行时间较长或服务器异常），请查看终端日志后重试"
    );
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
      ? `Agent 模式（${appRuntime?.platform || "跨平台"}）：正在规划并调用 MCP 工具…`
      : "正在回复..."
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
        messagesEl.scrollTop = messagesEl.scrollHeight;
      },
      onDone: (payload) => {
        if (payload?.time) {
          assistantEl.metaEl.textContent = `MassAgent · ${displayTime(payload.time)}`;
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
        applyCompletionStatus(payload);
      },
      onError: (msg) => {
        assistantEl.contentEl.textContent = msg;
      },
    });
    await fetchSessions();
    renderSessionList();
    await loadMessages(currentSessionId);
  } catch (err) {
    if (err.name === "AbortError") {
      const partial = (assistantEl.contentEl.textContent || "").trim();
      assistantEl.contentEl.textContent = partial
        ? partial + "\n\n⚠️ **[已终止]**"
        : "⚠️ **[已终止]**";
      statusText.className = "status-text status-warn";
      setStatus("已终止（后台将不再执行后续步骤）");
      try {
        await loadMessages(currentSessionId);
      } catch {
        /* ignore */
      }
    } else {
      statusText.className = "status-text status-error";
      setStatus(`失败：${err.message}`);
    }
  } finally {
    forceStopStreamingUI();
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (isSharedView) return;
  if (isStreaming) {
    setStatus("正在生成中，请先点「终止」或等待完成");
    return;
  }

  const text = promptInput.value.trim();
  if (!text && pendingFiles.length === 0) return;
  if (!currentSessionId) await bootSessionsAndLoad();

  try {
    setStatus(pendingFiles.length ? "正在上传附件..." : "正在发送...");
    const uploaded = await uploadPendingFiles(currentSessionId);
    const finalMessage = buildUserMessage(text, uploaded);

    promptInput.value = "";
    promptInput.style.height = "auto";
    toggleWelcomePanel(false);

    const useAgent = uploaded.length > 0 || /\[已上传附件\]/.test(finalMessage);
    await runAssistantStream({ userMessage: finalMessage, useAgent });
    // 从服务端加载消息（含正确 message id，便于后续编辑）
  } catch (err) {
    setStatus(`发送失败：${err.message}`);
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
  setStatus("已请求终止（当前正在跑的工具可能仍在终端输出片刻）");
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
    setStatus("正在创建新会话…");
    currentSessionId = await createSession({
      model: modelSelect.value || null,
      temperature: Number(tempInput.value || 0),
    });
    pendingFiles = [];
    renderAttachments();
    await fetchSessions();
    renderSessionList();
    await loadMessages(currentSessionId);
    updateBrowserUrl(currentSessionId, false);
    setStatus("");
  } catch (err) {
    setStatus(`创建会话失败：${err.message}`);
  }
});

clearSessionBtn.addEventListener("click", async () => {
  if (!currentSessionId || isSharedView) return;
  if (!confirm("确定清空当前会话？")) return;
  const res = await fetch(`/api/sessions/${currentSessionId}/clear`, { method: "POST" });
  if (!res.ok) throw new Error("清空失败");
  await fetchSessions();
  renderSessionList();
  await loadMessages(currentSessionId);
});

shareBtn.addEventListener("click", async () => {
  if (!currentSessionId || isSharedView) return;
  await enableShare(currentSessionId);
  await navigator.clipboard.writeText(buildShareUrl(currentSessionId));
  shareStatus.textContent = "已复制";
  await fetchSessions();
  renderSessionList();
});

exitShareViewBtn.addEventListener("click", () => {
  window.location.href = "/";
});

(async () => {
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
    setStatus(`页面加载失败：${err.message}`);
  }

  await sideTasks;
})();
