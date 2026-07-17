/* Sentri — Web Dashboard */

const API = "/api";

async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(API + path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

function toast(msg, isError = false) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.style.borderColor = isError ? "var(--red)" : "var(--accent)";
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 3500);
}

/* ── Watch ─────────────────────────────────────────── */

async function startWatch() {
  try {
    await api("POST", "/watch/start");
    toast("Watcher started");
    setTimeout(() => location.reload(), 800);
  } catch (e) { toast(e.message, true); }
}

async function stopWatch() {
  try {
    await api("POST", "/watch/stop");
    toast("Watcher stopped");
    setTimeout(() => location.reload(), 800);
  } catch (e) { toast(e.message, true); }
}

/* ── Auth ─────────────────────────────────────────── */

async function sendAuthCode() {
  const phone = document.getElementById("auth-phone").value.trim();
  if (!phone) return toast("Enter phone number", true);
  try {
    const data = await api("POST", "/auth/phone", { phone });
    toast(data.message);
    if (data.step === "code_sent") {
      document.getElementById("auth-step-code").classList.remove("hidden");
    } else if (data.step === "done") {
      setTimeout(() => location.reload(), 800);
    }
  } catch (e) { toast(e.message, true); }
}

async function submitAuthCode() {
  const code = document.getElementById("auth-code").value.trim();
  try {
    const data = await api("POST", "/auth/code", { code });
    toast(data.message);
    if (data.step === "needs_password") {
      document.getElementById("auth-step-password").classList.remove("hidden");
    } else if (data.step === "done") {
      setTimeout(() => location.reload(), 800);
    }
  } catch (e) { toast(e.message, true); }
}

async function submitAuthPassword() {
  const password = document.getElementById("auth-password").value;
  try {
    const data = await api("POST", "/auth/password", { password });
    toast(data.message);
    if (data.step === "done") setTimeout(() => location.reload(), 800);
  } catch (e) { toast(e.message, true); }
}

/* ── Destination ─────────────────────────────────── */

async function loadDialogs(targetId) {
  const el = document.getElementById(targetId);
  el.innerHTML = "<p class='hint'>Loading…</p>";
  el.classList.remove("hidden");
  try {
    const dialogs = await api("GET", "/telegram/dialogs");
    el.innerHTML = dialogs.map(d => `
      <div class="picker-item" onclick="setDestination(${d.id}, '${esc(d.name)}')">
        <span>${esc(d.name)}</span>
        <span class="meta">${d.id}</span>
      </div>
    `).join("");
  } catch (e) { el.innerHTML = `<p class='error-text'>${e.message}</p>`; }
}

async function setDestination(chatId, title) {
  try {
    await api("POST", "/config/destination", { chat_id: chatId, title });
    toast(`Destination set to ${title}`);
    setTimeout(() => location.reload(), 800);
  } catch (e) { toast(e.message, true); }
}

/* ── Groups ──────────────────────────────────────── */

async function loadTelegramGroups() {
  const el = document.getElementById("telegram-groups-picker");
  el.innerHTML = "<p class='hint'>Loading…</p>";
  el.classList.remove("hidden");
  try {
    const groups = await api("GET", "/telegram/groups");
    el.innerHTML = groups.map(g => `
      <div class="picker-item" onclick="addGroup(${g.id}, '${esc(g.name)}')">
        <span>${esc(g.name)}</span>
        <span class="meta">${g.id}</span>
      </div>
    `).join("");
  } catch (e) { el.innerHTML = `<p class='error-text'>${e.message}</p>`; }
}

async function addGroup(chatId, title) {
  try {
    await api("POST", "/groups", { chat_id: chatId, title, watch_mode: "selected_users" });
    toast(`Added group: ${title}`);
    setTimeout(() => location.reload(), 800);
  } catch (e) { toast(e.message, true); }
}

async function updateGroupMode(id, mode) {
  try {
    await api("PATCH", `/groups/${id}`, { watch_mode: mode });
    toast("Watch mode updated");
  } catch (e) { toast(e.message, true); }
}

async function toggleGroup(id, enabled) {
  try {
    await api("PATCH", `/groups/${id}`, { enabled });
    toast(enabled ? "Group enabled" : "Group disabled");
    setTimeout(() => location.reload(), 600);
  } catch (e) { toast(e.message, true); }
}

async function deleteGroup(id) {
  if (!confirm("Remove this group and all its watched users?")) return;
  try {
    await api("DELETE", `/groups/${id}`);
    toast("Group removed");
    setTimeout(() => location.reload(), 600);
  } catch (e) { toast(e.message, true); }
}

async function syncAdmins(id) {
  try {
    const data = await api("POST", `/groups/${id}/sync-admins`);
    toast(`Synced ${data.synced} admin(s)`);
  } catch (e) { toast(e.message, true); }
}

/* ── Users ───────────────────────────────────────── */

let currentGroupChatId = null;

function showUsers(groupId, title) {
  document.getElementById("users-group-id").value = groupId;
  document.getElementById("users-group-title").textContent = title;
  document.getElementById("users-panel").classList.remove("hidden");
  loadUsers(groupId);
  // find chat_id from table row
  const row = document.getElementById(`group-row-${groupId}`);
  if (row) {
    const code = row.querySelector("code");
    if (code) currentGroupChatId = parseInt(code.textContent);
  }
}

function hideUsers() {
  document.getElementById("users-panel").classList.add("hidden");
}

async function loadUsers(groupId) {
  const el = document.getElementById("users-table");
  try {
    const users = await api("GET", `/groups/${groupId}/users`);
    if (!users.length) {
      el.innerHTML = "<p class='hint'>No watched users. Add members below.</p>";
      return;
    }
    el.innerHTML = `<table class="table"><thead><tr>
      <th>User ID</th><th>Name</th><th>Username</th><th>Admin</th><th></th>
    </tr></thead><tbody>${users.map(u => `
      <tr>
        <td><code>${u.user_id}</code></td>
        <td>${esc(u.display_name)}</td>
        <td>${u.username ? '@' + esc(u.username) : '—'}</td>
        <td>${u.is_admin ? '✓' : ''}</td>
        <td><button class="btn btn-sm btn-danger" onclick="deleteUser(${u.id}, ${groupId})">Remove</button></td>
      </tr>
    `).join("")}</tbody></table>`;
  } catch (e) { el.innerHTML = `<p class='error-text'>${e.message}</p>`; }
}

async function loadParticipants() {
  if (!currentGroupChatId) return toast("Could not resolve group chat ID", true);
  const el = document.getElementById("participants-picker");
  el.innerHTML = "<p class='hint'>Loading…</p>";
  el.classList.remove("hidden");
  const groupId = document.getElementById("users-group-id").value;
  try {
    const parts = await api("GET", `/telegram/participants/${currentGroupChatId}`);
    el.innerHTML = parts.map(p => `
      <div class="picker-item" onclick="addUser(${groupId}, ${p.user_id}, '${esc(p.display_name)}', '${esc(p.username || '')}')">
        <span>${esc(p.display_name)}</span>
        <span class="meta">id:${p.user_id}</span>
      </div>
    `).join("");
  } catch (e) { el.innerHTML = `<p class='error-text'>${e.message}</p>`; }
}

async function addUser(groupId, userId, displayName, username) {
  try {
    await api("POST", `/groups/${groupId}/users`, {
      user_id: userId,
      display_name: displayName,
      username: username || null,
    });
    toast(`Added user id:${userId}`);
    loadUsers(groupId);
    document.getElementById("participants-picker").classList.add("hidden");
  } catch (e) { toast(e.message, true); }
}

async function deleteUser(userId, groupId) {
  try {
    await api("DELETE", `/users/${userId}`);
    toast("User removed");
    loadUsers(groupId);
  } catch (e) { toast(e.message, true); }
}

function esc(str) {
  return String(str || "").replace(/'/g, "\\'").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}