const state = {
  routers: [],
  selectedRouterId: null,
  clients: [],
  previousClients: new Map(),
  filter: "all",
  search: "",
};

const els = {
  subtitle: document.querySelector("#subtitle"),
  routerSelect: document.querySelector("#routerSelect"),
  refreshBtn: document.querySelector("#refreshBtn"),
  statusValue: document.querySelector("#statusValue"),
  clientCount: document.querySelector("#clientCount"),
  cpuValue: document.querySelector("#cpuValue"),
  ramValue: document.querySelector("#ramValue"),
  uptimeValue: document.querySelector("#uptimeValue"),
  searchInput: document.querySelector("#searchInput"),
  clientsBody: document.querySelector("#clientsBody"),
  segments: document.querySelectorAll(".segment"),
};

function formatPercent(value) {
  return value === null || value === undefined ? "-" : `${Number(value).toFixed(1)}%`;
}

function formatBytes(bytes) {
  if (bytes === null || bytes === undefined) return "-";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = Number(bytes);
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function formatSpeed(current, previous) {
  if (!current || !previous || current.bytes === null || previous.bytes === null) return "-";
  const seconds = (current.time - previous.time) / 1000;
  const delta = current.bytes - previous.bytes;
  if (seconds <= 0 || delta < 0) return "-";
  return `${formatBytes(delta / seconds)}/s`;
}

function formatUptime(seconds) {
  if (!seconds) return "-";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}g ${hours}s`;
  if (hours > 0) return `${hours}s ${minutes}d`;
  return `${minutes}d`;
}

function formatTime(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString("az-AZ", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    day: "2-digit",
    month: "2-digit",
  });
}

function signalClass(value) {
  if (value === null || value === undefined) return "";
  if (value >= -60) return "good";
  if (value >= -72) return "mid";
  return "bad";
}

function clientKey(client) {
  return client.mac || client.ip || client.hostname || Math.random().toString(36);
}

async function api(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

async function loadRouters() {
  state.routers = await api("/routers");
  if (!state.selectedRouterId && state.routers.length > 0) {
    state.selectedRouterId = state.routers[0].id;
  }
  renderRouterSelect();
}

async function loadDashboard() {
  if (!state.selectedRouterId) {
    renderEmpty("Router yoxdur");
    return;
  }

  const now = Date.now();
  const [status, clients] = await Promise.all([
    api(`/routers/${state.selectedRouterId}/status`).catch(() => null),
    api(`/routers/${state.selectedRouterId}/clients`),
  ]);

  const previous = new Map(state.previousClients);
  state.previousClients = new Map(
    clients.map((client) => [
      clientKey(client),
      {
        rx: { bytes: client.rx_bytes, time: now },
        tx: { bytes: client.tx_bytes, time: now },
      },
    ]),
  );
  state.clients = clients.map((client) => {
    const old = previous.get(clientKey(client));
    return {
      ...client,
      rx_speed: formatSpeed({ bytes: client.rx_bytes, time: now }, old?.rx),
      tx_speed: formatSpeed({ bytes: client.tx_bytes, time: now }, old?.tx),
    };
  });

  renderMetrics(status);
  renderClients();
}

function renderRouterSelect() {
  els.routerSelect.innerHTML = state.routers
    .map((router) => `<option value="${router.id}">${escapeHtml(router.name)} (${escapeHtml(router.host)})</option>`)
    .join("");
  els.routerSelect.value = state.selectedRouterId || "";
}

function renderMetrics(status) {
  const router = state.routers.find((item) => item.id === state.selectedRouterId);
  els.subtitle.textContent = router ? `${router.host} · ${formatTime(status?.last_seen)}` : "Router seçilməyib";
  els.statusValue.textContent = status?.online ? "Online" : "Offline";
  els.statusValue.style.color = status?.online ? "var(--accent)" : "var(--bad)";
  els.clientCount.textContent = state.clients.length.toString();
  els.cpuValue.textContent = formatPercent(status?.cpu_usage);
  els.ramValue.textContent = formatPercent(status?.ram_usage);
  els.uptimeValue.textContent = formatUptime(status?.uptime);
}

function renderClients() {
  const query = state.search.trim().toLowerCase();
  const rows = state.clients.filter((client) => {
    const typeMatch = state.filter === "all" || client.connection_type === state.filter;
    const text = `${client.hostname || ""} ${client.ip || ""} ${client.mac || ""}`.toLowerCase();
    return typeMatch && (!query || text.includes(query));
  });

  if (rows.length === 0) {
    renderEmpty("Client tapılmadı");
    return;
  }

  els.clientsBody.innerHTML = rows
    .map((client) => {
      const connection = client.connection_type || "unknown";
      const signal = client.signal === null || client.signal === undefined ? "-" : `${client.signal} dBm`;
      return `
        <tr>
          <td>
            <div class="clientName">${escapeHtml(client.hostname || "Adsız cihaz")}</div>
            <div class="muted">${escapeHtml(client.interface || "")}</div>
          </td>
          <td>${escapeHtml(client.ip || "-")}</td>
          <td>${escapeHtml(client.mac || "-")}</td>
          <td><span class="pill ${connection === "wifi" ? "wifi" : ""}">${escapeHtml(connection)}</span></td>
          <td class="signal ${signalClass(client.signal)}">${signal}</td>
          <td>${client.rx_speed}<div class="muted">${formatBytes(client.rx_bytes)}</div></td>
          <td>${client.tx_speed}<div class="muted">${formatBytes(client.tx_bytes)}</div></td>
          <td>${formatTime(client.last_seen)}</td>
        </tr>
      `;
    })
    .join("");
}

function renderEmpty(message) {
  els.clientsBody.innerHTML = `<tr><td colspan="8" class="empty">${escapeHtml(message)}</td></tr>`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
    return map[char];
  });
}

async function refresh() {
  els.refreshBtn.disabled = true;
  try {
    await loadRouters();
    await loadDashboard();
  } catch (error) {
    els.subtitle.textContent = error.message;
    renderEmpty("Məlumat yüklənmədi");
  } finally {
    els.refreshBtn.disabled = false;
  }
}

els.routerSelect.addEventListener("change", () => {
  state.selectedRouterId = els.routerSelect.value;
  state.previousClients.clear();
  loadDashboard();
});

els.refreshBtn.addEventListener("click", refresh);
els.searchInput.addEventListener("input", () => {
  state.search = els.searchInput.value;
  renderClients();
});

els.segments.forEach((button) => {
  button.addEventListener("click", () => {
    els.segments.forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.filter = button.dataset.filter;
    renderClients();
  });
});

refresh();
setInterval(loadDashboard, 2000);
