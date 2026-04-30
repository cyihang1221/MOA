const modelSelect = document.getElementById("modelSelect");
const tempInput = document.getElementById("tempInput");
const messagesEl = document.getElementById("messages");
const form = document.getElementById("chatForm");
const promptInput = document.getElementById("promptInput");
const sendButton = document.getElementById("sendButton");
const newSessionBtn = document.getElementById("newSessionBtn");
const clearSessionBtn = document.getElementById("clearSessionBtn");
const sessionListEl = document.getElementById("sessionList");
const statusText = document.getElementById("statusText");
const fileInput = document.getElementById("fileInput");
const analyzeBtn = document.getElementById("analyzeBtn");

let sessions = [];
let currentSessionId = null;

function nowString() {
  const now = new Date();
  return `${now.getHours().toString().padStart(2, "0")}:${now
    .getMinutes()
    .toString()
    .padStart(2, "0")}`;
}

function displayTime(t) {
  if (!t) return "";
  // 形如：2026-04-29T06:42:35+00:00 / 2026-04-29T06:42:35Z
  const m = String(t).match(/T(\d\d:\d\d)/);
  if (m && m[1]) return m[1];
  return String(t);
}

function setStatus(text) {
  statusText.textContent = text || "";
}

function assistantLabel() {
  return "助手";
}

function userLabel() {
  return "你";
}

function createMessageEl(role, content, timeStr = "") {
  const div = document.createElement("div");
  div.className = `message ${role}`;

  const contentEl = document.createElement("div");
  contentEl.textContent = content || "";

  const metaEl = document.createElement("div");
  metaEl.className = "message-meta";
  const label = role === "user" ? userLabel() : assistantLabel();
  metaEl.textContent = `${label} · ${displayTime(timeStr) || ""}`;

  div.appendChild(contentEl);
  div.appendChild(metaEl);
  messagesEl.appendChild(div);

  messagesEl.scrollTop = messagesEl.scrollHeight;
  return { div, contentEl, metaEl };
}

async function initModels() {
  try {
    const res = await fetch("/api/models");
    const data = await res.json();
    const models = data.models || [];

    if (models.length === 0 && data.default_model) {
      models.push(data.default_model);
    }

    if (models.length === 0) {
      modelSelect.innerHTML = "<option value=''>未配置模型</option>";
      setStatus("未读取到可用模型，请检查 .env 的 LLM_MODEL_ID");
      return;
    }

    modelSelect.innerHTML = "";
    models.forEach((model) => {
      const option = document.createElement("option");
      option.value = model;
      option.textContent = model;
      if (data.default_model && model === data.default_model) {
        option.selected = true;
      }
      modelSelect.appendChild(option);
    });
    setStatus("模型加载成功");
  } catch (err) {
    modelSelect.innerHTML = "<option value=''>模型加载失败</option>";
    setStatus("模型加载失败，请检查后端服务");
  }
}

async function fetchSessions() {
  const res = await fetch("/api/sessions");
  if (!res.ok) throw new Error("获取会话列表失败");
  const data = await res.json();
  sessions = data.sessions || [];
}

async function createSession({ title, model, temperature } = {}) {
  const res = await fetch("/api/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: title || "默认会话",
      model: model || null,
      temperature: Number(temperature || 0),
    }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "创建会话失败");
  return data.session_id;
}

async function deleteSession(sessionId) {
  const res = await fetch(`/api/sessions/${sessionId}`, { method: "DELETE" });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "删除会话失败");
}

async function renameSession(sessionId, title) {
  const res = await fetch(`/api/sessions/${sessionId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "重命名失败");
}

function renderSessionList() {
  sessionListEl.innerHTML = "";
  sessions.forEach((session) => {
    const item = document.createElement("div");
    item.className = `session-item ${session.id === currentSessionId ? "active" : ""}`;

    const titleEl = document.createElement("div");
    titleEl.className = "session-title";
    titleEl.textContent = session.title || "未命名会话";

    const actionsEl = document.createElement("div");
    actionsEl.className = "session-actions";

    const renameBtn = document.createElement("button");
    renameBtn.type = "button";
    renameBtn.className = "session-action-btn";
    renameBtn.textContent = "重命名";
    renameBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const newTitle = prompt("输入新的会话名称", session.title || "默认会话");
      if (!newTitle) return;
      try {
        await renameSession(session.id, newTitle.trim());
        await fetchSessions();
        currentSessionId = session.id;
        renderSessionList();
        await loadMessages(currentSessionId);
        setStatus("会话已重命名");
      } catch (err) {
        setStatus(`重命名失败：${err.message}`);
      }
    });

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "session-action-btn";
    deleteBtn.textContent = "删除";
    deleteBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const ok = confirm(`确定删除会话：${session.title || ""} ？`);
      if (!ok) return;
      try {
        await deleteSession(session.id);
        await bootSessionsAndLoad();
        setStatus("会话已删除");
      } catch (err) {
        setStatus(`删除失败：${err.message}`);
      }
    });

    item.appendChild(titleEl);
    actionsEl.appendChild(renameBtn);
    actionsEl.appendChild(deleteBtn);
    item.appendChild(actionsEl);

    item.addEventListener("click", async () => {
      currentSessionId = session.id;
      renderSessionList();
      await loadMessages(currentSessionId);
      setStatus("已切换会话");
    });

    sessionListEl.appendChild(item);
  });
}

function clearMessagesUI() {
  messagesEl.innerHTML = "";
}

async function loadMessages(sessionId) {
  clearMessagesUI();
  const res = await fetch(`/api/sessions/${sessionId}/messages`);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "加载会话消息失败");

  const msgs = data.messages || [];
  msgs.forEach((m) => {
    createMessageEl(m.role, m.content, m.time || "");
  });
}

async function bootSessionsAndLoad() {
  await fetchSessions();
  if (!sessions || sessions.length === 0) {
    const sessionId = await createSession({
      title: "默认会话",
      model: modelSelect.value || null,
      temperature: Number(tempInput.value || 0),
    });
    currentSessionId = sessionId;
    await fetchSessions();
  }
  // 如果当前会话还存在则保持选择；否则切到最新的会话
  const found = sessions.find((s) => s.id === currentSessionId);
  if (!found && sessions.length > 0) {
    currentSessionId = sessions[0].id;
  }
  renderSessionList();
  await loadMessages(currentSessionId);
}

async function streamChatAndRender({
  sessionId,
  userMessage,
  model,
  temperature,
  onDelta,
  onDone,
  onError,
}) {
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      user_message: userMessage,
      model: model || null,
      temperature: Number(temperature || 0),
    }),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "请求失败");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE 分隔符是空行：\n\n
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      const lines = part.split("\n");
      for (const line of lines) {
        if (!line.startsWith("data:")) continue;
        const dataStr = line.slice(5).trim();
        if (!dataStr) continue;

        let payload = null;
        try {
          payload = JSON.parse(dataStr);
        } catch {
          continue;
        }

        if (payload && payload.delta !== undefined) {
          onDelta(payload.delta);
        } else if (payload && payload.done) {
          onDone(payload);
        } else if (payload && payload.error) {
          onError(payload.error);
        }
      }
    }
  }
}

async function streamAnalyzeMgfAndRender({
  sessionId,
  file,
  onDelta,
  onDone,
  onError,
}) {
  const formData = new FormData();
  formData.append("session_id", sessionId);
  formData.append("file", file);

  const res = await fetch("/api/analyze/mgf/stream", {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "请求失败");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      const lines = part.split("\n");
      for (const line of lines) {
        if (!line.startsWith("data:")) continue;
        const dataStr = line.slice(5).trim();
        if (!dataStr) continue;

        let payload = null;
        try {
          payload = JSON.parse(dataStr);
        } catch {
          continue;
        }

        if (payload && payload.delta !== undefined) {
          onDelta(payload.delta);
        } else if (payload && payload.done) {
          onDone(payload);
        } else if (payload && payload.error) {
          onError(payload.error);
        }
      }
    }
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = promptInput.value.trim();
  if (!text) return;

  if (!currentSessionId) {
    await bootSessionsAndLoad();
  }
  const sessionId = currentSessionId;

  const userTime = nowString();
  createMessageEl("user", text, userTime);
  promptInput.value = "";
  promptInput.style.height = "auto";

  const assistantEl = createMessageEl("assistant", "", "");
  let assistantText = "";

  sendButton.disabled = true;
  sendButton.textContent = "发送中...";
  setStatus(`正在请求模型：${modelSelect.value || "默认模型"}`);

  try {
    await streamChatAndRender({
      sessionId,
      userMessage: text,
      model: modelSelect.value || null,
      temperature: Number(tempInput.value || 0),
      onDelta: (delta) => {
        assistantText += delta;
        assistantEl.contentEl.textContent = assistantText;
      },
      onDone: async (payload) => {
        if (payload && payload.time) {
          assistantEl.metaEl.textContent = `${assistantLabel()} · ${displayTime(
            payload.time
          )}`;
        } else if (payload && payload.error) {
          assistantEl.contentEl.textContent = payload.error;
        } else {
          assistantEl.metaEl.textContent = `${assistantLabel()} · ${nowString()}`;
        }
      },
      onError: (msg) => {
        assistantEl.contentEl.textContent = msg;
      },
    });

    setStatus("响应完成");
    // 让会话标题/列表顺序保持与后端一致
    await fetchSessions();
    renderSessionList();
    await loadMessages(sessionId);
  } catch (err) {
    const errMsg = `请求失败：${err.message}`;
    assistantEl.contentEl.textContent = errMsg;
    assistantEl.metaEl.textContent = `${assistantLabel()} · ${nowString()}`;
    setStatus("请求失败");
  } finally {
    sendButton.disabled = false;
    sendButton.textContent = "发送";
  }
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

newSessionBtn.addEventListener("click", async () => {
  try {
    const sessionId = await createSession({
      title: "默认会话",
      model: modelSelect.value || null,
      temperature: Number(tempInput.value || 0),
    });
    currentSessionId = sessionId;
    await fetchSessions();
    renderSessionList();
    await loadMessages(currentSessionId);
    setStatus("新会话已创建");
  } catch (err) {
    setStatus(`创建失败：${err.message}`);
  }
});

clearSessionBtn.addEventListener("click", async () => {
  if (!currentSessionId) return;
  const ok = confirm("确定清空当前会话？（不删除会话，仅清空消息）");
  if (!ok) return;
  try {
    const res = await fetch(`/api/sessions/${currentSessionId}/clear`, { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "清空失败");
    await fetchSessions();
    renderSessionList();
    await loadMessages(currentSessionId);
    setStatus("当前会话已清空");
  } catch (err) {
    setStatus(`清空失败：${err.message}`);
  }
});

(async () => {
  await initModels();
  await bootSessionsAndLoad();
})();

// 上传文件分析功能
const dropZone = document.getElementById("dropZone");
const uploadBtn = document.getElementById("uploadBtn");

uploadBtn.addEventListener("click", () => {
  fileInput.click();
});

fileInput.addEventListener("change", () => {
  if (fileInput.files.length > 0) {
    setStatus(`已选择文件: ${fileInput.files[0].name}`);
  }
});

// Drag and drop support
dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("dragover");
});

dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  const file = e.dataTransfer.files[0];
  if (file) {
    const dt = new DataTransfer();
    dt.items.add(file);
    fileInput.files = dt.files;
    setStatus(`已拖入文件: ${file.name}`);
  }
});

analyzeBtn.addEventListener("click", async () => {
  try {
    const file = fileInput.files && fileInput.files[0];
    if (!file) {
      setStatus("请先选择 .mgf / .raw 文件");
      return;
    }

    if (!currentSessionId) {
      await bootSessionsAndLoad();
    }

    const sessionId = currentSessionId;

    sendButton.disabled = true;
    analyzeBtn.disabled = true;
    setStatus(`正在上传并分析: ${file.name} ...`);

    const assistantEl = createMessageEl("assistant", "", "");
    let assistantText = "";

    await streamAnalyzeMgfAndRender({
      sessionId,
      file,
      onDelta: (delta) => {
        assistantText += delta;
        assistantEl.contentEl.textContent = assistantText;
      },
      onDone: async (payload) => {
        if (payload && payload.time) {
          assistantEl.metaEl.textContent = `${assistantLabel()} · ${displayTime(
            payload.time
          )}`;
        } else {
          assistantEl.metaEl.textContent = `${assistantLabel()} · ${nowString()}`;
        }

        await fetchSessions();
        renderSessionList();
        await loadMessages(sessionId);
        setStatus("分析完成");
        fileInput.value = ""; // 清空选择
      },
      onError: (errMsg) => {
        assistantEl.contentEl.textContent = errMsg;
        assistantEl.metaEl.textContent = `${assistantLabel()} · ${nowString()}`;
        setStatus("分析失败");
        fileInput.value = "";
      },
    });
  } catch (err) {
    setStatus(`分析请求失败：${err.message}`);
  } finally {
    sendButton.disabled = false;
    analyzeBtn.disabled = false;
  }
});
