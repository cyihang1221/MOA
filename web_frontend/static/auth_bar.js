const accountNameEl = document.getElementById("accountName");
const logoutBtn = document.getElementById("logoutBtn");

async function loadAccount() {
  if (!accountNameEl) return;
  const res = await fetch("/api/auth/me");
  if (!res.ok) {
    location.href = "/login";
    return;
  }
  const data = await res.json();
  accountNameEl.textContent = data.username || "";
  accountNameEl.title = "此账号的对话单独保存在自己的数据库中";
}

logoutBtn?.addEventListener("click", async () => {
  await fetch("/api/auth/logout", { method: "POST" });
  location.href = "/login";
});

loadAccount();
