const state = {
  routers: [],
  selectedRouterId: null,
  clients: [],
  metrics: [],
  ports: [],
  blockedClients: [],
  diagnostics: [],
  appUsers: [],
  status: null,
  summary: null,
  auth: JSON.parse(localStorage.getItem("keenetic-auth") || "null"),
  lang: localStorage.getItem("keenetic-lang") || "az",
  sectionPrefs: JSON.parse(localStorage.getItem("keenetic-section-prefs") || "{}"),
  viewScale: localStorage.getItem("keenetic-view-scale") || "normal",
  panelOrder: JSON.parse(localStorage.getItem("keenetic-panel-order") || "[]"),
  panelSizes: JSON.parse(localStorage.getItem("keenetic-panel-sizes") || "{}"),
  previousClients: new Map(),
  heavyLoadedAt: 0,
  dashboardLoading: false,
  dashboardNeedsHeavy: false,
  filter: "all",
  search: "",
};

const els = {
  subtitle: document.querySelector("#subtitle"),
  routerDescriptionText: document.querySelector("#routerDescriptionText"),
  routerTitleMeta: document.querySelector("#routerTitleMeta"),
  languageSelect: document.querySelector("#languageSelect"),
  routerSelect: document.querySelector("#routerSelect"),
  addSchoolBtn: document.querySelector("#addSchoolBtn"),
  pingBtn: document.querySelector("#pingBtn"),
  siteCheckBtn: document.querySelector("#siteCheckBtn"),
  adminPanelBtn: document.querySelector("#adminPanelBtn"),
  userBadge: document.querySelector("#userBadge"),
  logoutBtn: document.querySelector("#logoutBtn"),
  refreshBtn: document.querySelector("#refreshBtn"),
  loginModal: document.querySelector("#loginModal"),
  loginForm: document.querySelector("#loginForm"),
  loginUsernameInput: document.querySelector("#loginUsernameInput"),
  loginPasswordInput: document.querySelector("#loginPasswordInput"),
  loginMessage: document.querySelector("#loginMessage"),
  adminPanelModal: document.querySelector("#adminPanelModal"),
  adminPanelClose: document.querySelector("#adminPanelClose"),
  userForm: document.querySelector("#userForm"),
  newUserNameInput: document.querySelector("#newUserNameInput"),
  newUserPasswordInput: document.querySelector("#newUserPasswordInput"),
  newUserRoleSelect: document.querySelector("#newUserRoleSelect"),
  adminUsersList: document.querySelector("#adminUsersList"),
  adminUserCount: document.querySelector("#adminUserCount"),
  adminRouterName: document.querySelector("#adminRouterName"),
  adminRouterModel: document.querySelector("#adminRouterModel"),
  adminRouterVersion: document.querySelector("#adminRouterVersion"),
  adminRouterHost: document.querySelector("#adminRouterHost"),
  adminRouterSelect: document.querySelector("#adminRouterSelect"),
  routerDescriptionForm: document.querySelector("#routerDescriptionForm"),
  routerNameInput: document.querySelector("#routerNameInput"),
  routerHostInput: document.querySelector("#routerHostInput"),
  routerPortInput: document.querySelector("#routerPortInput"),
  routerUsernameInput: document.querySelector("#routerUsernameInput"),
  routerPasswordInput: document.querySelector("#routerPasswordInput"),
  routerAccessMethodSelect: document.querySelector("#routerAccessMethodSelect"),
  routerDescriptionInput: document.querySelector("#routerDescriptionInput"),
  routerAddressInput: document.querySelector("#routerAddressInput"),
  routerContactNameInput: document.querySelector("#routerContactNameInput"),
  routerContactPhoneInput: document.querySelector("#routerContactPhoneInput"),
  routerSupportStatusSelect: document.querySelector("#routerSupportStatusSelect"),
  routerEnabledInput: document.querySelector("#routerEnabledInput"),
  refreshIdentityBtn: document.querySelector("#refreshIdentityBtn"),
  osChannelSelect: document.querySelector("#osChannelSelect"),
  osCheckBtn: document.querySelector("#osCheckBtn"),
  osUpdateBtn: document.querySelector("#osUpdateBtn"),
  osUpdateStatus: document.querySelector("#osUpdateStatus"),
  adminPingHostInput: document.querySelector("#adminPingHostInput"),
  adminSiteUrlInput: document.querySelector("#adminSiteUrlInput"),
  adminRouterTestBtn: document.querySelector("#adminRouterTestBtn"),
  adminRouterPingBtn: document.querySelector("#adminRouterPingBtn"),
  adminInternetPingBtn: document.querySelector("#adminInternetPingBtn"),
  adminSiteCheckBtn: document.querySelector("#adminSiteCheckBtn"),
  adminToolsExportBtn: document.querySelector("#adminToolsExportBtn"),
  adminToolsStatus: document.querySelector("#adminToolsStatus"),
  userModalMessage: document.querySelector("#userModalMessage"),
  pingModal: document.querySelector("#pingModal"),
  pingForm: document.querySelector("#pingForm"),
  pingModalClose: document.querySelector("#pingModalClose"),
  pingHostInput: document.querySelector("#pingHostInput"),
  pingCountInput: document.querySelector("#pingCountInput"),
  pingWarning: document.querySelector("#pingWarning"),
  pingResult: document.querySelector("#pingResult"),
  pingExportBtn: document.querySelector("#pingExportBtn"),
  siteCheckModal: document.querySelector("#siteCheckModal"),
  siteCheckForm: document.querySelector("#siteCheckForm"),
  siteCheckModalClose: document.querySelector("#siteCheckModalClose"),
  siteUrlInput: document.querySelector("#siteUrlInput"),
  siteWarning: document.querySelector("#siteWarning"),
  siteResult: document.querySelector("#siteResult"),
  siteExportBtn: document.querySelector("#siteExportBtn"),
  schoolModal: document.querySelector("#schoolModal"),
  schoolForm: document.querySelector("#schoolForm"),
  schoolModalClose: document.querySelector("#schoolModalClose"),
  schoolIpInput: document.querySelector("#schoolIpInput"),
  schoolLoginInput: document.querySelector("#schoolLoginInput"),
  schoolPasswordInput: document.querySelector("#schoolPasswordInput"),
  schoolDescriptionInput: document.querySelector("#schoolDescriptionInput"),
  schoolModalMessage: document.querySelector("#schoolModalMessage"),
  testSchoolBtn: document.querySelector("#testSchoolBtn"),
  confirmSchoolBtn: document.querySelector("#confirmSchoolBtn"),
  statusValue: document.querySelector("#statusValue"),
  clientCount: document.querySelector("#clientCount"),
  cpuValue: document.querySelector("#cpuValue"),
  ramValue: document.querySelector("#ramValue"),
  uptimeValue: document.querySelector("#uptimeValue"),
  totalTrafficValue: document.querySelector("#totalTrafficValue"),
  lanTrafficValue: document.querySelector("#lanTrafficValue"),
  wifiTrafficValue: document.querySelector("#wifiTrafficValue"),
  maxTrafficValue: document.querySelector("#maxTrafficValue"),
  maxClientValue: document.querySelector("#maxClientValue"),
  wifiForm: document.querySelector("#wifiForm"),
  wifiInfoList: document.querySelector("#wifiInfoList"),
  wifiSsidInput: document.querySelector("#wifiSsidInput"),
  wifiSsidBtn: document.querySelector("#wifiSsidBtn"),
  wifiPasswordInput: document.querySelector("#wifiPasswordInput"),
  wifiOffBtn: document.querySelector("#wifiOffBtn"),
  wifiOnBtn: document.querySelector("#wifiOnBtn"),
  restartBtn: document.querySelector("#restartBtn"),
  actionMessage: document.querySelector("#actionMessage"),
  alertBar: document.querySelector("#alertBar"),
  dashboardGrid: document.querySelector("#dashboardGrid"),
  supportStatusBadge: document.querySelector("#supportStatusBadge"),
  supportSiteName: document.querySelector("#supportSiteName"),
  supportAddress: document.querySelector("#supportAddress"),
  supportContact: document.querySelector("#supportContact"),
  supportRouterLine: document.querySelector("#supportRouterLine"),
  diagnoseBtn: document.querySelector("#diagnoseBtn"),
  diagnosticResult: document.querySelector("#diagnosticResult"),
  portsList: document.querySelector("#portsList"),
  blockedList: document.querySelector("#blockedList"),
  searchInput: document.querySelector("#searchInput"),
  clientsBody: document.querySelector("#clientsBody"),
  tableWrap: document.querySelector(".tableWrap"),
  viewScaleSelect: document.querySelector("#viewScaleSelect"),
  sectionToggles: document.querySelectorAll(".sectionToggle"),
  segments: document.querySelectorAll(".segment"),
};

const translations = {
  az: {
    action: "Əməl",
    addSchool: "Yeni məktəb",
    addSchoolHint: "Router məlumatlarını yaz, əvvəl test et, sonra təsdiqlə.",
    all: "Hamısı",
    allow: "Aç",
    anonymousDevice: "Adsız cihaz",
    block: "Blokla",
    blocked: "bloklandı",
    blockedDevices: "Bloklanmış avadanlıqlar",
    blockedNotFound: "Bloklanmış avadanlıq yoxdur",
    blocking: "bloklanır",
    change: "Dəyiş",
    changeName: "Adı dəyiş",
    clientFilters: "Client filterləri",
    clientList: "Client siyahısı",
    clients: "Client",
    clientNotFound: "Client tapılmadı",
    connection: "Bağlantı",
    connectionType: "Connection type",
    confirm: "Təsdiq et",
    dataLoadFailed: "Məlumat yüklənmədi",
    description: "Müəssisə adı",
    lastSeen: "Son görülmə",
    hide: "Gizlət",
    show: "Göstər",
    loading: "Yüklənir",
    loadingRouters: "Router və clientlər yüklənir",
    newWifiPassword: "Yeni Wi-Fi şifrəsi",
    newWifiName: "Yeni Wi-Fi adı",
    noPorts: "Port tapılmadı",
    noTraffic: "Məlumat gözlənilir",
    noRouter: "Router yoxdur",
    notSelected: "Router seçilməyib",
    opened: "açıldı",
    opening: "açılır",
    other: "Digər",
    password: "Parol",
    ports: "Portlar",
    refresh: "Refresh",
    routerControls: "Router idarəsi",
    routerAdded: "Router əlavə olundu",
    routerAdding: "Router əlavə edilir",
    routerStatus: "Router status",
    routerTestOk: "Test uğurludur",
    routerTesting: "Router test edilir",
    searchPlaceholder: "Client, IP və ya MAC axtar",
    status: "Status",
    test: "Test et",
    uptime: "Uptime",
    wifiPasswordChanged: "Wi-Fi şifrəsi dəyişdi",
    wifiPasswordChanging: "Wi-Fi şifrəsi dəyişir",
    wifiNameChanged: "Wi-Fi adı dəyişdi",
    wifiNameChanging: "Wi-Fi adı dəyişir",
    wifiOff: "Wi-Fi söndür",
    wifiOn: "Wi-Fi aç",
    wifiTurningOff: "Wi-Fi söndürülür",
    wifiTurningOn: "Wi-Fi açılır",
    wifiTurnedOff: "Wi-Fi söndürüldü",
    wifiTurnedOn: "Wi-Fi açıldı",
    portOff: "Söndür",
    portOn: "Aç",
    portTurningOff: "Port söndürülür",
    portTurningOn: "Port açılır",
    portTurnedOff: "Port söndürüldü",
    portTurnedOn: "Port açıldı",
    protectedWan: "WAN qorunur",
    restartRouter: "Router restart",
    restartConfirm: "Router restart edilsin?",
    restartingRouter: "Router restart edilir",
    routerRestarted: "Restart əmri göndərildi",
    traffic: "Trafik",
    totalTraffic: "Ümumi trafik",
    lanTraffic: "LAN trafik",
    wifiTraffic: "Wi-Fi trafik",
    lan: "LAN",
    wifi: "Wi-Fi",
    unknown: "Digər",
  },
  ru: {
    action: "Действие",
    addSchool: "Новая школа",
    addSchoolHint: "Введите данные роутера, сначала проверьте, затем подтвердите.",
    all: "Все",
    allow: "Открыть",
    anonymousDevice: "Без имени",
    block: "Блок",
    blocked: "заблокирован",
    blockedDevices: "Заблокированные устройства",
    blockedNotFound: "Заблокированных устройств нет",
    blocking: "блокируется",
    change: "Изменить",
    changeName: "Изменить имя",
    clientFilters: "Фильтры клиентов",
    clientList: "Список клиентов",
    clients: "Клиенты",
    clientNotFound: "Клиент не найден",
    connection: "Подключение",
    connectionType: "Тип подключения",
    confirm: "Подтвердить",
    dataLoadFailed: "Данные не загрузились",
    description: "Название учреждения",
    lastSeen: "Последний раз",
    hide: "Скрыть",
    show: "Показать",
    loading: "Загрузка",
    loadingRouters: "Загрузка роутеров и клиентов",
    newWifiPassword: "Новый пароль Wi-Fi",
    newWifiName: "Новое имя Wi-Fi",
    noPorts: "Порты не найдены",
    noTraffic: "Ожидание данных",
    noRouter: "Роутер не найден",
    notSelected: "Роутер не выбран",
    opened: "открыт",
    opening: "открывается",
    other: "Другое",
    password: "Пароль",
    ports: "Порты",
    refresh: "Обновить",
    routerControls: "Управление роутером",
    routerAdded: "Роутер добавлен",
    routerAdding: "Роутер добавляется",
    routerStatus: "Статус роутера",
    routerTestOk: "Тест успешен",
    routerTesting: "Проверка роутера",
    searchPlaceholder: "Поиск по клиенту, IP или MAC",
    status: "Статус",
    test: "Проверить",
    uptime: "Аптайм",
    wifiPasswordChanged: "Пароль Wi-Fi изменен",
    wifiPasswordChanging: "Пароль Wi-Fi меняется",
    wifiNameChanged: "Имя Wi-Fi изменено",
    wifiNameChanging: "Имя Wi-Fi меняется",
    wifiOff: "Выключить Wi-Fi",
    wifiOn: "Включить Wi-Fi",
    wifiTurningOff: "Wi-Fi выключается",
    wifiTurningOn: "Wi-Fi включается",
    wifiTurnedOff: "Wi-Fi выключен",
    wifiTurnedOn: "Wi-Fi включен",
    portOff: "Выключить",
    portOn: "Включить",
    portTurningOff: "Порт выключается",
    portTurningOn: "Порт включается",
    portTurnedOff: "Порт выключен",
    portTurnedOn: "Порт включен",
    protectedWan: "WAN защищен",
    restartRouter: "Рестарт роутера",
    restartConfirm: "Перезапустить роутер?",
    restartingRouter: "Роутер перезапускается",
    routerRestarted: "Команда перезапуска отправлена",
    traffic: "Трафик",
    totalTraffic: "Общий трафик",
    lanTraffic: "LAN трафик",
    wifiTraffic: "Wi-Fi трафик",
    lan: "LAN",
    wifi: "Wi-Fi",
    unknown: "Другое",
  },
  en: {
    action: "Action",
    addSchool: "New school",
    addSchoolHint: "Enter router details, test first, then confirm.",
    all: "All",
    allow: "Allow",
    anonymousDevice: "Unnamed device",
    block: "Block",
    blocked: "blocked",
    blockedDevices: "Blocked devices",
    blockedNotFound: "No blocked devices",
    blocking: "blocking",
    change: "Change",
    changeName: "Change name",
    clientFilters: "Client filters",
    clientList: "Client list",
    clients: "Clients",
    clientNotFound: "Client not found",
    connection: "Connection",
    connectionType: "Connection type",
    confirm: "Confirm",
    dataLoadFailed: "Data failed to load",
    description: "Institution name",
    lastSeen: "Last seen",
    hide: "Hide",
    show: "Show",
    loading: "Loading",
    loadingRouters: "Loading routers and clients",
    newWifiPassword: "New Wi-Fi password",
    newWifiName: "New Wi-Fi name",
    noPorts: "No ports found",
    noTraffic: "Waiting for data",
    noRouter: "No router",
    notSelected: "Router not selected",
    opened: "allowed",
    opening: "allowing",
    other: "Other",
    password: "Password",
    ports: "Ports",
    refresh: "Refresh",
    routerControls: "Router controls",
    routerAdded: "Router added",
    routerAdding: "Adding router",
    routerStatus: "Router status",
    routerTestOk: "Test successful",
    routerTesting: "Testing router",
    searchPlaceholder: "Search client, IP or MAC",
    status: "Status",
    test: "Test",
    uptime: "Uptime",
    wifiPasswordChanged: "Wi-Fi password changed",
    wifiPasswordChanging: "Changing Wi-Fi password",
    wifiNameChanged: "Wi-Fi name changed",
    wifiNameChanging: "Changing Wi-Fi name",
    wifiOff: "Turn Wi-Fi off",
    wifiOn: "Turn Wi-Fi on",
    wifiTurningOff: "Turning Wi-Fi off",
    wifiTurningOn: "Turning Wi-Fi on",
    wifiTurnedOff: "Wi-Fi turned off",
    wifiTurnedOn: "Wi-Fi turned on",
    portOff: "Turn off",
    portOn: "Turn on",
    portTurningOff: "Turning port off",
    portTurningOn: "Turning port on",
    portTurnedOff: "Port turned off",
    portTurnedOn: "Port turned on",
    protectedWan: "WAN protected",
    restartRouter: "Restart router",
    restartConfirm: "Restart router?",
    restartingRouter: "Restarting router",
    routerRestarted: "Restart command sent",
    traffic: "Traffic",
    totalTraffic: "Total traffic",
    lanTraffic: "LAN traffic",
    wifiTraffic: "Wi-Fi traffic",
    lan: "LAN",
    wifi: "Wi-Fi",
    unknown: "Other",
  },
};

function t(key) {
  return translations[state.lang]?.[key] || translations.az[key] || key;
}

function applyTranslations() {
  document.documentElement.lang = state.lang;
  els.languageSelect.value = state.lang;
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.placeholder = t(node.dataset.i18nPlaceholder);
  });
  document.querySelectorAll("[data-i18n-aria]").forEach((node) => {
    node.setAttribute("aria-label", t(node.dataset.i18nAria));
  });
  applyViewPrefs();
}

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

function formatBits(bits) {
  if (bits === null || bits === undefined) return "-";
  const units = ["bps", "Kbps", "Mbps", "Gbps"];
  let value = Number(bits);
  let unit = 0;
  while (value >= 1000 && unit < units.length - 1) {
    value /= 1000;
    unit += 1;
  }
  return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function formatUptime(seconds) {
  if (!seconds) return "-";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const labels = {
    az: { day: "g", hour: "s", minute: "d" },
    ru: { day: "д", hour: "ч", minute: "м" },
    en: { day: "d", hour: "h", minute: "m" },
  }[state.lang];
  if (days > 0) return `${days}${labels.day} ${hours}${labels.hour}`;
  if (hours > 0) return `${hours}${labels.hour} ${minutes}${labels.minute}`;
  return `${minutes}${labels.minute}`;
}

function formatTime(value) {
  if (!value) return "-";
  const locale = { az: "az-AZ", ru: "ru-RU", en: "en-US" }[state.lang];
  return new Date(value).toLocaleString(locale, {
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

function isAdmin() {
  return state.auth?.role === "admin";
}

function isSupport() {
  return ["admin", "first_support"].includes(state.auth?.role);
}

function applyAuthState() {
  document.body.dataset.role = state.auth?.role || "";
  els.loginModal.classList.toggle("hidden", Boolean(state.auth?.token));
  els.adminPanelBtn.textContent = "Admin panel";
  els.userBadge.textContent = state.auth ? `${state.auth.username} · ${state.auth.role}` : "-";
}

async function api(path, options = {}) {
  const { noAuth, ...fetchOptions } = options;
  const headers = new Headers(fetchOptions.headers || {});
  if (state.auth?.token && !noAuth) headers.set("Authorization", `Bearer ${state.auth.token}`);
  const response = await fetch(path, { cache: "no-store", ...fetchOptions, headers });
  if (!response.ok) {
    let detail = "";
    try {
      const data = await response.json();
      detail = data?.detail ? `: ${data.detail}` : "";
    } catch (_) {
      detail = "";
    }
    if (response.status === 401 && !noAuth) {
      state.auth = null;
      localStorage.removeItem("keenetic-auth");
      applyAuthState();
      throw new Error("Sessiya bitib. Zəhmət olmasa yenidən daxil ol.");
    }
    throw new Error(`${path}: HTTP ${response.status}${detail}`);
  }
  return response.json();
}

async function login() {
  els.loginMessage.textContent = "Yoxlanılır...";
  const result = await api("/auth/login", {
    noAuth: true,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: els.loginUsernameInput.value.trim(),
      password: els.loginPasswordInput.value,
    }),
  });
  state.auth = result;
  localStorage.setItem("keenetic-auth", JSON.stringify(result));
  els.loginPasswordInput.value = "";
  els.loginMessage.textContent = "";
  applyAuthState();
  await refresh();
}

function logout() {
  state.auth = null;
  localStorage.removeItem("keenetic-auth");
  applyAuthState();
}

async function openAdminPanel() {
  els.userForm.reset();
  els.newUserRoleSelect.value = "user";
  els.userModalMessage.textContent = "";
  els.osUpdateStatus.textContent = "Hazırdır";
  els.adminToolsStatus.textContent = "Test nəticələri burada görünəcək.";
  els.adminToolsExportBtn.disabled = true;
  renderAdminRouter();
  els.adminPanelModal.classList.remove("hidden");
  await loadAdminUsers();
}

function closeAdminPanel() {
  els.adminPanelModal.classList.add("hidden");
}

async function loadAdminUsers() {
  state.appUsers = await api("/users");
  renderAdminUsers();
}

function renderAdminUsers() {
  els.adminUserCount.textContent = `${state.appUsers.length} hesab`;
  if (!state.appUsers.length) {
    els.adminUsersList.innerHTML = '<span class="muted">İstifadəçi yoxdur</span>';
    return;
  }
  els.adminUsersList.innerHTML = state.appUsers
    .map((user) => `
      <div class="adminUserItem">
        <div>
          <strong>${escapeHtml(user.username)}</strong>
          <span>${escapeHtml(user.role)} · ${user.enabled ? "aktiv" : "bağlı"}</span>
        </div>
        <select class="userRoleSelect" data-user-id="${escapeHtml(user.id)}">
          <option value="user" ${user.role === "user" ? "selected" : ""}>İstifadəçi</option>
          <option value="call_center" ${user.role === "call_center" ? "selected" : ""}>Call center</option>
          <option value="first_support" ${user.role === "first_support" ? "selected" : ""}>First support</option>
          <option value="admin" ${user.role === "admin" ? "selected" : ""}>Admin</option>
        </select>
        <button class="userToggleBtn" type="button" data-user-id="${escapeHtml(user.id)}" data-enabled="${user.enabled ? "false" : "true"}">
          ${user.enabled ? "Bağla" : "Aktiv et"}
        </button>
        <button class="dangerBtn userDeleteBtn" type="button" data-user-id="${escapeHtml(user.id)}">Sil</button>
      </div>
    `)
    .join("");
}

function renderAdminRouter() {
  const router = state.routers.find((item) => item.id === state.selectedRouterId);
  els.adminRouterSelect.innerHTML = state.routers
    .map((item) => {
      const label = [item.name, item.description].filter(Boolean).join(" - ");
      return `<option value="${escapeHtml(item.id)}">${escapeHtml(label || item.host)} (${escapeHtml(item.host)})</option>`;
    })
    .join("");
  els.adminRouterSelect.value = state.selectedRouterId || "";
  els.adminRouterName.textContent = router?.name || "-";
  els.adminRouterModel.textContent = router?.model || "-";
  els.adminRouterVersion.textContent = router?.firmware_version || "-";
  els.adminRouterHost.textContent = router?.host || "-";
  els.routerNameInput.value = router?.name || "";
  els.routerHostInput.value = router?.host || "";
  els.routerPortInput.value = router?.port || 80;
  els.routerUsernameInput.value = router?.username || "admin";
  els.routerPasswordInput.value = "";
  els.routerAccessMethodSelect.value = router?.access_method || "vpn";
  els.routerDescriptionInput.value = router?.description || "";
  els.routerAddressInput.value = router?.address || "";
  els.routerContactNameInput.value = router?.contact_name || "";
  els.routerContactPhoneInput.value = router?.contact_phone || "";
  els.routerSupportStatusSelect.value = router?.support_status || "normal";
  els.routerEnabledInput.checked = router?.enabled !== false;
  if (!els.adminPingHostInput.value) els.adminPingHostInput.value = "8.8.8.8";
  if (!els.adminSiteUrlInput.value) els.adminSiteUrlInput.value = "google.com";
}

async function saveRouterSettings() {
  if (!state.selectedRouterId) return;
  els.osUpdateStatus.textContent = "Router məlumatları saxlanılır...";
  const payload = {
    name: els.routerNameInput.value.trim(),
    host: els.routerHostInput.value.trim(),
    port: Number(els.routerPortInput.value || 80),
    username: els.routerUsernameInput.value.trim(),
    access_method: els.routerAccessMethodSelect.value,
    description: els.routerDescriptionInput.value.trim(),
    address: els.routerAddressInput.value.trim(),
    contact_name: els.routerContactNameInput.value.trim(),
    contact_phone: els.routerContactPhoneInput.value.trim(),
    support_status: els.routerSupportStatusSelect.value,
    enabled: els.routerEnabledInput.checked,
  };
  if (els.routerPasswordInput.value) {
    payload.password = els.routerPasswordInput.value;
  }
  const router = await api(`/routers/${state.selectedRouterId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  state.routers = state.routers.map((item) => item.id === router.id ? router : item);
  state.selectedRouterId = router.id;
  renderRouterSelect();
  renderAdminRouter();
  renderSupportPanel();
  renderMetrics(state.status, state.summary);
  els.osUpdateStatus.textContent = "Router məlumatları saxlanıldı.";
}

async function createAppUser() {
  els.userModalMessage.textContent = "Əlavə edilir...";
  await api("/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: els.newUserNameInput.value.trim(),
      password: els.newUserPasswordInput.value,
      role: els.newUserRoleSelect.value,
      enabled: true,
    }),
  });
  els.userModalMessage.textContent = "İstifadəçi əlavə olundu";
  els.newUserPasswordInput.value = "";
  await loadAdminUsers();
}

async function updateAppUser(userId, payload) {
  await api(`/users/${userId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await loadAdminUsers();
}

async function deleteAppUser(userId) {
  if (!window.confirm("İstifadəçi silinsin?")) return;
  const response = await fetch(`/users/${encodeURIComponent(userId)}`, {
    method: "DELETE",
    headers: state.auth?.token ? { Authorization: `Bearer ${state.auth.token}` } : {},
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`/users/${userId}: HTTP ${response.status}`);
  await loadAdminUsers();
}

async function refreshRouterIdentity() {
  if (!state.selectedRouterId) return;
  els.osUpdateStatus.textContent = "Router məlumatları yenilənir...";
  const router = await api(`/routers/${state.selectedRouterId}/refresh-identity`, { method: "POST" });
  state.routers = state.routers.map((item) => item.id === router.id ? router : item);
  renderRouterSelect();
  renderMetrics(state.status, state.summary);
  renderAdminRouter();
  els.osUpdateStatus.textContent = "Router məlumatları yeniləndi.";
}

async function checkRouterOs() {
  if (!state.selectedRouterId) return;
  els.osUpdateStatus.textContent = "OS yenilənməsi yoxlanır...";
  const result = await api(`/routers/${state.selectedRouterId}/os/check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ channel: els.osChannelSelect.value }),
  });
  await loadRouters();
  renderAdminRouter();
  els.osUpdateStatus.textContent = formatOsResult(result);
}

async function updateRouterOs() {
  if (!state.selectedRouterId) return;
  if (!window.confirm("KeeneticOS yenilənsin? Router reboot edə bilər və bir müddət əlçatmaz ola bilər.")) return;
  els.osUpdateStatus.textContent = "OS yeniləmə əmri göndərilir...";
  const result = await api(`/routers/${state.selectedRouterId}/os/update`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ channel: els.osChannelSelect.value }),
  });
  els.osUpdateStatus.textContent = formatOsResult(result);
}

function formatOsResult(result) {
  const current = result.current || result.after_check || {};
  const update = result.update || {};
  return [
    `Status: ${result.status || "-"}`,
    `Kanal: ${result.channel || "-"}`,
    `Model: ${current.model || "-"}`,
    `Hazırki versiya: ${update.current_version || current.release || current.title || "-"}`,
    `Mövcud versiya: ${update.available_version || "-"}`,
    `Update: ${update.update_available ? "var" : "yoxdur"}`,
    `Növbədə komponent: ${update.queued_count ?? "-"}`,
    result.message ? `Mesaj: ${result.message}` : "",
  ].filter(Boolean).join("\n");
}

function schoolPayload() {
  const name = els.schoolDescriptionInput.value.trim();
  return {
    name,
    description: name,
    site: name,
    host: els.schoolIpInput.value.trim(),
    port: 80,
    username: els.schoolLoginInput.value.trim(),
    password: els.schoolPasswordInput.value,
    access_method: "vpn",
    enabled: true,
  };
}

function openSchoolModal(defaults = {}) {
  els.schoolForm.reset();
  els.schoolIpInput.value = defaults.host || "";
  els.schoolLoginInput.value = defaults.username || "admin";
  els.schoolPasswordInput.value = defaults.password || "";
  els.schoolDescriptionInput.value = defaults.name || "";
  els.confirmSchoolBtn.disabled = true;
  els.schoolModalMessage.textContent = "";
  els.schoolModal.classList.remove("hidden");
  els.schoolIpInput.focus();
}

function closeSchoolModal() {
  els.schoolModal.classList.add("hidden");
}

function openPingModal() {
  els.pingForm.reset();
  els.pingHostInput.value = "8.8.8.8";
  els.pingCountInput.value = "4";
  els.pingWarning.textContent = "";
  els.pingResult.textContent = "";
  els.pingExportBtn.disabled = true;
  els.pingModal.classList.remove("hidden");
  els.pingHostInput.focus();
}

function closePingModal() {
  els.pingModal.classList.add("hidden");
}

async function runPing() {
  if (!state.selectedRouterId) return;
  els.pingResult.textContent = "Routerdən ping...";
  els.pingWarning.textContent = "";
  els.pingExportBtn.disabled = true;
  const result = await api(`/routers/${state.selectedRouterId}/cli-ping`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      host: els.pingHostInput.value.trim(),
      count: Number(els.pingCountInput.value || 4),
    }),
  });
  const lines = [
    `${result.host} (${result.method})`,
    "Mənbə: Router CLI",
    `avg=${result.avg_ms ?? "-"} ms loss=${result.loss_percent ?? "-"}%`,
    result.output || JSON.stringify(result, null, 2),
  ];
  els.pingResult.textContent = lines.join("\n");
  els.pingWarning.textContent = result.warning ? "Xəbərdarlıq: ping gecikməsi 120 ms-dən yüksəkdir." : "";
  els.pingExportBtn.disabled = false;
}

async function adminRunRouterTest() {
  if (!state.selectedRouterId) return;
  els.adminToolsStatus.textContent = "Router RCI test edilir...";
  els.adminToolsExportBtn.disabled = true;
  const result = await api(`/routers/${state.selectedRouterId}/test`, { method: "POST" });
  els.adminToolsStatus.textContent = `Router RCI test: ${result.status || "ok"}`;
  els.adminToolsExportBtn.disabled = false;
}

async function adminRunPing(host) {
  if (!state.selectedRouterId) return;
  els.adminToolsStatus.textContent = `${host} ping edilir...`;
  els.adminToolsExportBtn.disabled = true;
  const result = await api(`/routers/${state.selectedRouterId}/cli-ping`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ host, count: 4 }),
  });
  els.adminToolsStatus.textContent = [
    `${result.host} (${result.method})`,
    "Mənbə: Router CLI",
    `Status: ${result.ok ? "əlçatandır" : "əlçatmaz"}`,
    `avg=${result.avg_ms ?? "-"} ms loss=${result.loss_percent ?? "-"}%`,
    result.output || JSON.stringify(result, null, 2),
  ].join("\n");
  els.adminToolsExportBtn.disabled = false;
}

async function adminRunServerPing(host) {
  if (!state.selectedRouterId) return;
  els.adminToolsStatus.textContent = `${host} serverdən ping edilir...`;
  els.adminToolsExportBtn.disabled = true;
  const result = await api(`/routers/${state.selectedRouterId}/ping`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ host, count: 4 }),
  });
  els.adminToolsStatus.textContent = [
    `${result.host} (${result.method})`,
    "Mənbə: Monitor server",
    `Status: ${result.ok ? "əlçatandır" : "əlçatmaz"}`,
    `avg=${result.avg_ms ?? "-"} ms loss=${result.loss_percent ?? "-"}%`,
    result.output || JSON.stringify(result, null, 2),
  ].join("\n");
  els.adminToolsExportBtn.disabled = false;
}

async function adminRunSiteCheck() {
  els.adminToolsStatus.textContent = "Routerdən sayt ping yoxlanır...";
  els.adminToolsExportBtn.disabled = true;
  const result = await api(`/routers/${state.selectedRouterId}/cli-site-check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: els.adminSiteUrlInput.value.trim() || "google.com" }),
  });
  els.adminToolsStatus.textContent = [
    `URL: ${result.url}`,
    `Host: ${result.host}`,
    `Metod: ${result.method}`,
    `Status: ${result.ok ? "əlçatandır" : "əlçatmaz"}`,
    `Ping: ${result.avg_ms ?? "-"} ms · loss=${result.loss_percent ?? "-"}%`,
    `Mesaj: ${result.message || "-"}`,
    "",
    result.output || JSON.stringify(result, null, 2),
  ].join("\n");
  els.adminToolsExportBtn.disabled = false;
}

function openSiteCheckModal() {
  els.siteCheckForm.reset();
  els.siteUrlInput.value = "google.com";
  els.siteWarning.textContent = "";
  els.siteResult.textContent = "";
  els.siteExportBtn.disabled = true;
  els.siteCheckModal.classList.remove("hidden");
  els.siteUrlInput.focus();
}

function closeSiteCheckModal() {
  els.siteCheckModal.classList.add("hidden");
}

async function runSiteCheck() {
  els.siteResult.textContent = "Routerdən sayt ping yoxlanır...";
  els.siteWarning.textContent = "";
  els.siteExportBtn.disabled = true;
  const result = await api(`/routers/${state.selectedRouterId}/cli-site-check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: els.siteUrlInput.value.trim() }),
  });
  const lines = [
    `URL: ${result.url}`,
    `Host: ${result.host}`,
    `Metod: ${result.method}`,
    `Status: ${result.ok ? "əlçatandır" : "əlçatmaz"}`,
    `Ping: ${result.avg_ms ?? "-"} ms · loss=${result.loss_percent ?? "-"}%`,
    `Mesaj: ${result.message || "-"}`,
    "",
    result.output || JSON.stringify(result, null, 2),
  ];
  els.siteResult.textContent = lines.join("\n");
  els.siteWarning.textContent = result.warning ? "Xəbərdarlıq: sayt gec cavab verir və ya əlçatmazdır." : "";
  els.siteExportBtn.disabled = false;
}

function exportText(filename, text) {
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function testSchoolRouter() {
  const payload = schoolPayload();
  els.schoolModalMessage.textContent = t("routerTesting");
  els.testSchoolBtn.disabled = true;
  els.confirmSchoolBtn.disabled = true;
  try {
    const result = await api("/routers/test-credentials", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        host: payload.host,
        port: payload.port,
        username: payload.username,
        password: payload.password,
      }),
    });
    els.schoolModalMessage.textContent = `${t("routerTestOk")}${result.model ? ` · ${result.model}` : ""}`;
    els.confirmSchoolBtn.disabled = false;
  } catch (error) {
    els.schoolModalMessage.textContent = error.message;
  } finally {
    els.testSchoolBtn.disabled = false;
  }
}

async function confirmSchoolRouter() {
  const payload = schoolPayload();
  els.schoolModalMessage.textContent = t("routerAdding");
  els.confirmSchoolBtn.disabled = true;
  const router = await api("/routers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  state.selectedRouterId = router.id;
  els.schoolModalMessage.textContent = t("routerAdded");
  await loadRouters();
  await loadDashboard({ forceHeavy: true });
  closeSchoolModal();
}

async function loadRouters() {
  state.routers = await api("/routers");
  if (!state.selectedRouterId && state.routers.length > 0) {
    state.selectedRouterId = state.routers[0].id;
  }
  renderRouterSelect();
}

async function loadDashboard(options = {}) {
  if (state.dashboardLoading) {
    if (options.forceHeavy) state.dashboardNeedsHeavy = true;
    return;
  }
  state.dashboardLoading = true;
  try {
    if (!state.selectedRouterId) {
      renderEmpty(t("noRouter"));
      renderPorts([]);
      renderBlockedClients([]);
      return;
    }

    const now = Date.now();
    const forceHeavy = Boolean(options.forceHeavy);
    const loadHeavy = forceHeavy || !state.heavyLoadedAt || now - state.heavyLoadedAt > 60000;
    const [status, clients, summary, blockedClients, diagnostics, ports, wifiInfo] = await Promise.all([
      api(`/routers/${state.selectedRouterId}/status`).catch(() => null),
      api(`/routers/${state.selectedRouterId}/clients`).catch(() => []),
      api(`/routers/${state.selectedRouterId}/summary`).catch(() => null),
      api(`/routers/${state.selectedRouterId}/blocked-clients`).catch(() => []),
      api(`/routers/${state.selectedRouterId}/diagnostics`).catch(() => []),
      loadHeavy ? api(`/routers/${state.selectedRouterId}/ports`).catch(() => []) : Promise.resolve(state.ports),
      loadHeavy ? api(`/routers/${state.selectedRouterId}/wifi`).catch(() => []) : Promise.resolve(null),
    ]);
    const clientRows = Array.isArray(clients) ? clients : [];

    const previous = new Map(state.previousClients);
    state.previousClients = new Map(
      clientRows.map((client) => [
        clientKey(client),
        {
          rx: { bytes: client.rx_bytes, time: now },
          tx: { bytes: client.tx_bytes, time: now },
        },
      ]),
    );
    state.clients = clientRows.map((client) => {
      const old = previous.get(clientKey(client));
      return {
        ...client,
        rx_speed: formatSpeed({ bytes: client.rx_bytes, time: now }, old?.rx),
        tx_speed: formatSpeed({ bytes: client.tx_bytes, time: now }, old?.tx),
      };
    });
    state.ports = Array.isArray(ports) ? ports : [];
    state.status = status;
    state.summary = summary;
    state.blockedClients = Array.isArray(blockedClients) ? blockedClients : [];
    state.diagnostics = Array.isArray(diagnostics) ? diagnostics : [];
    if (loadHeavy) state.heavyLoadedAt = now;

    renderMetrics(status, summary);
    renderSupportPanel();
    if (Array.isArray(wifiInfo)) renderWifiInfo(wifiInfo);
    renderPorts(state.ports);
    renderBlockedClients(state.blockedClients);
    renderClients();
    renderAlerts();
    if (loadHeavy) loadClientMetrics();
  } finally {
    state.dashboardLoading = false;
    if (state.dashboardNeedsHeavy) {
      state.dashboardNeedsHeavy = false;
      await loadDashboard({ forceHeavy: true });
    }
  }
}

function renderAlerts() {
  const wifiCount = state.clients.filter((client) => client.connection_type === "wifi").length;
  const alerts = [];
  if (wifiCount > 20) alerts.push(`Wi-Fi client sayı ${wifiCount}-dir. Limit 20-ni keçib.`);
  if (!alerts.length) {
    els.alertBar.classList.add("hidden");
    els.alertBar.textContent = "";
    return;
  }
  els.alertBar.textContent = alerts.join(" ");
  els.alertBar.classList.remove("hidden");
}

function renderWifiInfo(rows) {
  if (!rows.length) {
    els.wifiInfoList.innerHTML = `<span class="muted">${escapeHtml(t("noTraffic"))}</span>`;
    return;
  }
  els.wifiInfoList.innerHTML = rows
    .map((row) => `
      <div class="wifiInfoItem">
        <span>${escapeHtml(row.name || row.id)}</span>
        <strong>${escapeHtml(row.ssid || "-")}</strong>
      </div>
    `)
    .join("");
}

async function loadClientMetrics() {
  if (!state.selectedRouterId) return;
  try {
    state.metrics = await api(`/routers/${state.selectedRouterId}/client-metrics?limit=600`);
    renderClients();
  } catch (_error) {
    state.metrics = [];
  }
}

function renderRouterSelect() {
  els.routerSelect.innerHTML = state.routers
    .map((router) => {
      const label = [router.name, router.description].filter(Boolean).join(" - ");
      return `<option value="${router.id}">${escapeHtml(label || router.host)} (${escapeHtml(router.host)})</option>`;
    })
    .join("");
  els.routerSelect.value = state.selectedRouterId || "";
}

function renderMetrics(status, summary) {
  const router = state.routers.find((item) => item.id === state.selectedRouterId);
  const routerMeta = [router?.name, router?.model, router?.firmware_version].filter(Boolean).join(" · ");
  els.routerTitleMeta.textContent = routerMeta || "-";
  els.subtitle.textContent = router ? `${router.host} · ${formatTime(status?.last_seen)}` : t("notSelected");
  els.routerDescriptionText.textContent = router?.description || "Router qeydi yoxdur";
  els.routerDescriptionText.title = router?.description || "";
  els.statusValue.textContent = status?.online ? "Online" : "Offline";
  els.statusValue.style.color = status?.online ? "var(--accent)" : "var(--bad)";
  els.clientCount.textContent = String(summary?.client_count ?? state.clients.length);
  els.cpuValue.textContent = formatPercent(status?.cpu_usage);
  setLoadClass(els.cpuValue, status?.cpu_usage);
  els.ramValue.textContent = formatPercent(status?.ram_usage);
  setLoadClass(els.ramValue, status?.ram_usage);
  els.uptimeValue.textContent = formatUptime(status?.uptime);
  els.totalTrafficValue.innerHTML = formatTrafficPair(summary?.total_rx_bps, summary?.total_tx_bps);
  els.lanTrafficValue.innerHTML = formatTrafficPair(summary?.lan_rx_bps, summary?.lan_tx_bps);
  els.wifiTrafficValue.innerHTML = formatTrafficPair(summary?.wifi_rx_bps, summary?.wifi_tx_bps);
  els.maxTrafficValue.textContent = formatBits(summary?.max_traffic_bps);
  els.maxClientValue.textContent = String(summary?.max_client_count ?? summary?.client_count ?? state.clients.length);
}

function setLoadClass(element, value) {
  element.classList.remove("loadNormal", "loadWarning", "loadCritical");
  if (value === null || value === undefined || Number.isNaN(Number(value))) return;
  const numeric = Number(value);
  if (numeric >= 85) {
    element.classList.add("loadCritical");
  } else if (numeric >= 70) {
    element.classList.add("loadWarning");
  } else {
    element.classList.add("loadNormal");
  }
}

function renderSupportPanel() {
  const router = state.routers.find((item) => item.id === state.selectedRouterId);
  const lastDiagnostic = state.diagnostics[0];
  const badgeState = lastDiagnostic?.status || router?.support_status || "normal";
  els.supportStatusBadge.textContent = badgeState;
  els.supportStatusBadge.className = `supportStatusBadge ${badgeState}`;
  els.supportSiteName.textContent = router?.name || "-";
  els.supportAddress.textContent = router?.address || router?.description || "-";
  els.supportContact.textContent = [router?.contact_name, router?.contact_phone].filter(Boolean).join(" · ") || "-";
  els.supportRouterLine.textContent = router ? `${router.host} · ${router.model || "-"} · ${router.firmware_version || "-"}` : "-";
  if (lastDiagnostic) {
    els.diagnosticResult.textContent = formatDiagnostic(lastDiagnostic);
  } else {
    els.diagnosticResult.textContent = "Diaqnostika nəticəsi burada görünəcək.";
  }
}

function formatDiagnostic(row) {
  const result = row.result || {};
  const tests = result.tests || {};
  const status = result.status || {};
  const warnings = Array.isArray(result.warnings) ? result.warnings : [];
  const testLine = (label, test, detail = "") => {
    const state = test?.ok ? "OK" : "FAIL";
    const latency = test?.avg_ms === undefined || test?.avg_ms === null ? "" : ` · ${test.avg_ms} ms`;
    return `${label.padEnd(18, " ")} ${state}${latency}${detail}`;
  };
  return [
    "ÜMUMİ NƏTİCƏ",
    row.summary,
    "",
    "STATUS",
    `Vəziyyət: ${row.status.toUpperCase()} · ${formatTime(row.created_at)} · ${row.created_by || "-"}`,
    `WAN: ${status.wan_status || "-"} · ${status.wan_ip || "-"}`,
    `Resurs: CPU ${formatPercent(status.cpu_usage)} · RAM ${formatPercent(status.ram_usage)} · Uptime ${formatUptime(status.uptime)}`,
    `Client sayı: ${result.client_count ?? "-"}`,
    "",
    "TESTLƏR",
    testLine("Router ping", tests.router_ping),
    testLine("RCI giriş", tests.rci),
    testLine("Internet ping", tests.internet_ping),
    testLine("DNS", tests.dns),
    testLine("Sayt ping", tests.site),
    "",
    "XƏBƏRDARLIQ",
    warnings.length ? warnings.join("; ") : "Yoxdur",
    "",
    "OPERATOR QEYDİ",
    result.operator_script || "",
  ].join("\n");
}

async function runOneClickDiagnostic() {
  if (!state.selectedRouterId) return;
  els.diagnosticResult.textContent = "Diaqnostika işləyir...";
  els.diagnoseBtn.disabled = true;
  try {
    const result = await api(`/routers/${state.selectedRouterId}/diagnose`, { method: "POST" });
    state.diagnostics = [result, ...state.diagnostics].slice(0, 10);
    renderSupportPanel();
  } finally {
    els.diagnoseBtn.disabled = false;
  }
}


function formatTrafficPair(rx, tx) {
  if (rx === null && tx === null) return `<span class="muted">${escapeHtml(t("noTraffic"))}</span>`;
  if (rx === undefined && tx === undefined) return `<span class="muted">${escapeHtml(t("noTraffic"))}</span>`;
  return `<span class="rxRate">↓ ${formatBits(rx)}</span><span class="txRate">↑ ${formatBits(tx)}</span>`;
}

function renderPorts(ports = state.ports) {
  const rows = ports.filter((port) => {
    if (port.kind === "Port" || port.kind === "WifiMaster") return true;
    if (port.kind !== "AccessPoint") return false;
    return port.connected || port.state === "up" || Boolean(port.ssid);
  });
  if (rows.length === 0) {
    els.portsList.innerHTML = `<span class="muted">${escapeHtml(t("noPorts"))}</span>`;
    return;
  }
  els.portsList.innerHTML = rows
    .map((port) => {
      const active = port.connected || port.state === "up";
      const isWan = port.is_wan || port.category === "wan";
      const detail = port.kind === "Port"
        ? `${port.link || "-"}${port.speed_mbps ? ` · ${port.speed_mbps}M` : ""}${port.role ? ` · ${port.role}` : ""}`
        : `${port.state || "-"}${port.ssid ? ` · ${port.ssid}` : ""}`;
      const action = isWan
        ? `<span class="wanLock">${escapeHtml(t("protectedWan"))}</span>`
        : !isAdmin()
          ? '<span class="muted">-</span>'
        : `<button class="${active ? "dangerBtn" : "allowBtn"} portPowerBtn" type="button" data-interface-id="${escapeHtml(port.id)}" data-enabled="${active ? "false" : "true"}">
            ${escapeHtml(active ? t("portOff") : t("portOn"))}
          </button>`;
      return `
        <div class="portItem ${active ? "active" : "down"} ${escapeHtml(port.category || "access")}">
          <span class="portDot"></span>
          <strong>${escapeHtml(port.label || port.id)}</strong>
          <span class="portDetail">${escapeHtml(detail)}</span>
          ${action}
        </div>
      `;
    })
    .join("");
}

function renderBlockedClients(blockedClients = state.blockedClients) {
  if (blockedClients.length === 0) {
    els.blockedList.innerHTML = `<span class="muted">${escapeHtml(t("blockedNotFound"))}</span>`;
    return;
  }
  els.blockedList.innerHTML = blockedClients
    .map((client) => `
      <div class="blockedItem">
        <div>
          <strong>${escapeHtml(client.hostname || t("anonymousDevice"))}</strong>
          <span>${escapeHtml(client.ip || "-")} · ${escapeHtml(client.mac)}</span>
        </div>
        <button class="allowBtn unblockBtn" type="button" data-mac="${escapeHtml(client.mac)}">${escapeHtml(t("allow"))}</button>
      </div>
    `)
    .join("");
}

function renderClients() {
  const query = state.search.trim().toLowerCase();
  const rows = state.clients.filter((client) => {
    const typeMatch = state.filter === "all" || client.connection_type === state.filter;
    const text = `${client.hostname || ""} ${client.ip || ""} ${client.mac || ""}`.toLowerCase();
    return typeMatch && (!query || text.includes(query));
  });

  if (rows.length === 0) {
    renderEmpty(t("clientNotFound"));
    return;
  }

  els.clientsBody.innerHTML = rows
    .map((client) => {
      const connection = client.connection_type || "unknown";
      const connectionLabel = t(connection) || connection;
      const signal = client.signal === null || client.signal === undefined ? "-" : `${client.signal} dBm`;
      return `
        <tr>
          <td>
            <div class="clientName">${escapeHtml(client.hostname || t("anonymousDevice"))}</div>
            <div class="muted">${escapeHtml(client.interface || "")}</div>
          </td>
          <td>${escapeHtml(client.ip || "-")}</td>
          <td>${escapeHtml(client.mac || "-")}</td>
          <td><span class="pill ${connection === "wifi" ? "wifi" : connection === "lan" ? "lan" : ""}">${escapeHtml(connectionLabel)}</span></td>
          <td class="signal ${signalClass(client.signal)}">${signal}</td>
          <td>${client.rx_speed}<div class="muted">${formatBytes(client.rx_bytes)}</div></td>
          <td>${client.tx_speed}<div class="muted">${formatBytes(client.tx_bytes)}</div></td>
          <td>${renderSparkline(client)}</td>
          <td>${formatTime(client.last_seen)}</td>
          <td>${renderClientAction(client)}</td>
        </tr>
      `;
    })
    .join("");
}

function renderEmpty(message) {
  els.clientsBody.innerHTML = `<tr><td colspan="10" class="empty">${escapeHtml(message)}</td></tr>`;
}

function renderClientAction(client) {
  if (!isSupport()) return '<span class="muted">-</span>';
  if (!client.mac) return '<span class="muted">-</span>';
  return `
    <button class="dangerBtn clientBlockBtn" type="button" data-mac="${escapeHtml(client.mac)}" data-blocked="true">${escapeHtml(t("block"))}</button>
    <button class="allowBtn clientBlockBtn" type="button" data-mac="${escapeHtml(client.mac)}" data-blocked="false">${escapeHtml(t("allow"))}</button>
  `;
}

async function updateClientAccess(mac, blocked) {
  if (!state.selectedRouterId) return;
  setMessage(`${mac} ${blocked ? t("blocking") : t("opening")}`);
  await api(`/routers/${state.selectedRouterId}/clients/access`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mac, blocked }),
  });
  setMessage(`${mac} ${blocked ? t("blocked") : t("opened")}`);
  await loadDashboard({ forceHeavy: true });
}

async function updateWifiPassword(password) {
  if (!state.selectedRouterId) return;
  setMessage(t("wifiPasswordChanging"));
  await api(`/routers/${state.selectedRouterId}/wifi/password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  els.wifiPasswordInput.value = "";
  setMessage(t("wifiPasswordChanged"));
  await loadDashboard({ forceHeavy: true });
}

async function updateWifiSsid(ssid) {
  if (!state.selectedRouterId) return;
  setMessage(t("wifiNameChanging"));
  await api(`/routers/${state.selectedRouterId}/wifi/ssid`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ssid }),
  });
  els.wifiSsidInput.value = "";
  setMessage(t("wifiNameChanged"));
  await loadDashboard({ forceHeavy: true });
}

async function updateWifiPower(enabled) {
  if (!state.selectedRouterId) return;
  setMessage(enabled ? t("wifiTurningOn") : t("wifiTurningOff"));
  await api(`/routers/${state.selectedRouterId}/wifi/power`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
  setMessage(enabled ? t("wifiTurnedOn") : t("wifiTurnedOff"));
  await loadDashboard({ forceHeavy: true });
}

async function updatePortPower(interfaceId, enabled) {
  if (!state.selectedRouterId) return;
  setMessage(enabled ? t("portTurningOn") : t("portTurningOff"));
  await api(`/routers/${state.selectedRouterId}/interfaces/${encodeURIComponent(interfaceId)}/power`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
  setMessage(enabled ? t("portTurnedOn") : t("portTurnedOff"));
  await loadDashboard({ forceHeavy: true });
}

async function restartRouter() {
  if (!state.selectedRouterId) return;
  if (!window.confirm(t("restartConfirm"))) return;
  setMessage(t("restartingRouter"));
  await api(`/routers/${state.selectedRouterId}/restart`, { method: "POST" });
  setMessage(t("routerRestarted"));
}

function setMessage(message) {
  els.actionMessage.textContent = message;
}

function saveSectionPrefs() {
  localStorage.setItem("keenetic-section-prefs", JSON.stringify(state.sectionPrefs));
}

function applyViewPrefs() {
  document.querySelectorAll("[data-panel]").forEach((panel) => {
    const key = panel.dataset.panel;
    panel.classList.toggle("sectionHidden", state.sectionPrefs[key] === false);
  });
  els.sectionToggles.forEach((toggle) => {
    const key = toggle.dataset.targetPanel;
    toggle.checked = state.sectionPrefs[key] !== false;
  });
  document.body.classList.remove("viewCompact", "viewComfortable");
  if (state.viewScale === "compact") document.body.classList.add("viewCompact");
  if (state.viewScale === "comfortable") document.body.classList.add("viewComfortable");
  els.viewScaleSelect.value = state.viewScale;
}

function panelCards() {
  return Array.from(document.querySelectorAll("[data-card]"));
}

function savePanelOrder() {
  state.panelOrder = panelCards().map((panel) => panel.dataset.card);
  localStorage.setItem("keenetic-panel-order", JSON.stringify(state.panelOrder));
}

function applyPanelOrder() {
  if (!els.dashboardGrid || !Array.isArray(state.panelOrder) || !state.panelOrder.length) return;
  const cards = new Map(panelCards().map((panel) => [panel.dataset.card, panel]));
  state.panelOrder.forEach((key) => {
    const card = cards.get(key);
    if (card) els.dashboardGrid.appendChild(card);
  });
}

function defaultPanelSize(key) {
  if (["customer", "diagnostics", "status", "traffic", "wifi", "ports"].includes(key)) return "wide";
  if (key === "blocked") return "full";
  return "normal";
}

function panelSizeLabel(size) {
  if (size === "full") return "Tam";
  if (size === "wide") return "Geniş";
  return "Normal";
}

function savePanelSizes() {
  localStorage.setItem("keenetic-panel-sizes", JSON.stringify(state.panelSizes));
}

function applyPanelSizes() {
  panelCards().forEach((panel) => {
    const size = state.panelSizes[panel.dataset.card] || defaultPanelSize(panel.dataset.card);
    panel.classList.toggle("panelWide", size === "wide");
    panel.classList.toggle("panelFull", size === "full");
    panel.classList.toggle("panelNormal", size === "normal");
    const button = panel.querySelector(".panelSizeBtn");
    if (button) {
      button.textContent = panelSizeLabel(size);
      button.title = "Panel ölçüsü: Normal / Geniş / Tam";
    }
  });
}

function cyclePanelSize(panel) {
  const key = panel.dataset.card;
  const current = state.panelSizes[key] || defaultPanelSize(key);
  const next = current === "normal" ? "wide" : current === "wide" ? "full" : "normal";
  state.panelSizes[key] = next;
  savePanelSizes();
  applyPanelSizes();
}

function initDraggablePanels() {
  let dragged = null;
  panelCards().forEach((panel) => {
    const header = panel.querySelector(".panelHeader");
    if (!header) return;
    if (!header.querySelector(".panelSizeBtn")) {
      const button = document.createElement("button");
      button.className = "panelSizeBtn";
      button.type = "button";
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        cyclePanelSize(panel);
      });
      header.appendChild(button);
    }
    header.draggable = true;
    header.title = "Tutub sürüşdür";
    header.addEventListener("dragstart", (event) => {
      if (event.target.closest("button, input, select, textarea, a")) {
        event.preventDefault();
        return;
      }
      dragged = panel;
      panel.classList.add("dragging");
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", panel.dataset.card);
    });
    header.addEventListener("dragend", () => {
      panel.classList.remove("dragging");
      panelCards().forEach((item) => item.classList.remove("dragOver"));
      dragged = null;
      savePanelOrder();
    });
    panel.addEventListener("dragover", (event) => {
      if (!dragged || dragged === panel) return;
      event.preventDefault();
      panel.classList.add("dragOver");
      const rect = panel.getBoundingClientRect();
      const after = event.clientY > rect.top + rect.height / 2;
      els.dashboardGrid.insertBefore(dragged, after ? panel.nextSibling : panel);
    });
    panel.addEventListener("dragleave", () => {
      panel.classList.remove("dragOver");
    });
    panel.addEventListener("drop", (event) => {
      event.preventDefault();
      panel.classList.remove("dragOver");
      savePanelOrder();
    });
  });
}

function renderSparkline(client) {
  const key = clientKey(client);
  const rows = state.metrics.filter((row) => row.client_key === key).slice(-30);
  const rxRates = rateSeries(rows, "rx_bytes");
  const txRates = rateSeries(rows, "tx_bytes");
  if (rxRates.length < 2 && txRates.length < 2) return '<span class="muted">-</span>';
  return `
    <svg class="spark" viewBox="0 0 118 32" aria-label="Traffic trend">
      <path class="rx" d="${sparkPath(rxRates, 118, 32)}"></path>
      <path class="tx" d="${sparkPath(txRates, 118, 32)}"></path>
    </svg>
  `;
}

function rateSeries(rows, field) {
  const rates = [];
  for (let index = 1; index < rows.length; index += 1) {
    const previous = rows[index - 1];
    const current = rows[index];
    if (previous[field] === null || previous[field] === undefined || current[field] === null || current[field] === undefined) {
      rates.push(null);
      continue;
    }
    const seconds = (new Date(current.time) - new Date(previous.time)) / 1000;
    const delta = Number(current[field]) - Number(previous[field]);
    rates.push(seconds > 0 && delta >= 0 ? delta / seconds : null);
  }
  return rates;
}

function sparkPath(values, width, height) {
  const usable = values.map((value) => (value === null || value === undefined ? null : Number(value)));
  const numeric = usable.filter((value) => value !== null);
  if (numeric.length < 2) return "";
  const min = Math.min(...numeric);
  const max = Math.max(...numeric);
  const range = max - min || 1;
  const step = width / Math.max(usable.length - 1, 1);
  let fallback = min;
  return usable
    .map((value, index) => {
      if (value === null) value = fallback;
      fallback = value;
      const x = Math.round(index * step);
      const y = Math.round(height - ((value - min) / range) * (height - 4) - 2);
      return `${index === 0 ? "M" : "L"}${x},${y}`;
    })
    .join(" ");
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
    await loadDashboard({ forceHeavy: true });
  } catch (error) {
    els.subtitle.textContent = error.message;
    renderMetrics(null, null);
    renderPorts([]);
    renderBlockedClients([]);
    renderEmpty(t("dataLoadFailed"));
    renderAlerts();
  } finally {
    els.refreshBtn.disabled = false;
  }
}

els.routerSelect.addEventListener("change", () => {
  state.selectedRouterId = els.routerSelect.value;
  state.previousClients.clear();
  state.heavyLoadedAt = 0;
  loadDashboard({ forceHeavy: true });
});

els.addSchoolBtn.addEventListener("click", () => openSchoolModal());
els.schoolModalClose.addEventListener("click", closeSchoolModal);
els.schoolModal.addEventListener("click", (event) => {
  if (event.target === els.schoolModal) closeSchoolModal();
});
els.testSchoolBtn.addEventListener("click", () => {
  testSchoolRouter().catch((error) => {
    els.schoolModalMessage.textContent = error.message;
    els.testSchoolBtn.disabled = false;
  });
});
els.schoolForm.addEventListener("input", () => {
  els.confirmSchoolBtn.disabled = true;
});
els.schoolForm.addEventListener("submit", (event) => {
  event.preventDefault();
  confirmSchoolRouter().catch((error) => {
    els.schoolModalMessage.textContent = error.message;
    els.confirmSchoolBtn.disabled = false;
  });
});

els.loginForm.addEventListener("submit", (event) => {
  event.preventDefault();
  login().catch((error) => {
    els.loginMessage.textContent = error.message;
  });
});

els.logoutBtn.addEventListener("click", logout);
els.adminPanelBtn.addEventListener("click", () => {
  openAdminPanel().catch((error) => {
    els.userModalMessage.textContent = error.message;
  });
});
els.adminPanelClose.addEventListener("click", closeAdminPanel);
els.adminPanelModal.addEventListener("click", (event) => {
  if (event.target === els.adminPanelModal) closeAdminPanel();
});
els.userForm.addEventListener("submit", (event) => {
  event.preventDefault();
  createAppUser().catch((error) => {
    els.userModalMessage.textContent = error.message;
  });
});
els.adminUsersList.addEventListener("change", (event) => {
  const select = event.target.closest(".userRoleSelect");
  if (!select) return;
  updateAppUser(select.dataset.userId, { role: select.value }).catch((error) => {
    els.userModalMessage.textContent = error.message;
  });
});
els.adminUsersList.addEventListener("click", (event) => {
  const toggle = event.target.closest(".userToggleBtn");
  const deleteBtn = event.target.closest(".userDeleteBtn");
  if (toggle) {
    updateAppUser(toggle.dataset.userId, { enabled: toggle.dataset.enabled === "true" }).catch((error) => {
      els.userModalMessage.textContent = error.message;
    });
  }
  if (deleteBtn) {
    deleteAppUser(deleteBtn.dataset.userId).catch((error) => {
      els.userModalMessage.textContent = error.message;
    });
  }
});
els.refreshIdentityBtn.addEventListener("click", () => {
  refreshRouterIdentity().catch((error) => {
    els.osUpdateStatus.textContent = error.message;
  });
});
els.adminRouterSelect.addEventListener("change", () => {
  state.selectedRouterId = els.adminRouterSelect.value;
  state.previousClients.clear();
  state.heavyLoadedAt = 0;
  renderRouterSelect();
  renderAdminRouter();
  loadDashboard({ forceHeavy: true }).catch((error) => {
    els.osUpdateStatus.textContent = error.message;
  });
});
els.routerDescriptionForm.addEventListener("submit", (event) => {
  event.preventDefault();
  saveRouterSettings().catch((error) => {
    els.osUpdateStatus.textContent = error.message;
  });
});
els.osCheckBtn.addEventListener("click", () => {
  checkRouterOs().catch((error) => {
    els.osUpdateStatus.textContent = error.message;
  });
});
els.osUpdateBtn.addEventListener("click", () => {
  updateRouterOs().catch((error) => {
    els.osUpdateStatus.textContent = error.message;
  });
});
els.adminRouterTestBtn.addEventListener("click", () => {
  adminRunRouterTest().catch((error) => {
    els.adminToolsStatus.textContent = error.message;
  });
});
els.adminRouterPingBtn.addEventListener("click", () => {
  const router = state.routers.find((item) => item.id === state.selectedRouterId);
  adminRunServerPing(router?.host || els.adminPingHostInput.value.trim()).catch((error) => {
    els.adminToolsStatus.textContent = error.message;
  });
});
els.adminInternetPingBtn.addEventListener("click", () => {
  adminRunPing(els.adminPingHostInput.value.trim() || "8.8.8.8").catch((error) => {
    els.adminToolsStatus.textContent = error.message;
  });
});
els.adminSiteCheckBtn.addEventListener("click", () => {
  adminRunSiteCheck().catch((error) => {
    els.adminToolsStatus.textContent = error.message;
  });
});
els.adminToolsExportBtn.addEventListener("click", () => {
  exportText("admin-test-result.txt", els.adminToolsStatus.textContent || "");
});

els.pingBtn.addEventListener("click", openPingModal);
els.pingModalClose.addEventListener("click", closePingModal);
els.pingModal.addEventListener("click", (event) => {
  if (event.target === els.pingModal) closePingModal();
});
els.pingForm.addEventListener("submit", (event) => {
  event.preventDefault();
  runPing().catch((error) => {
    els.pingResult.textContent = error.message;
  });
});
els.pingExportBtn.addEventListener("click", () => {
  exportText("ping-result.txt", els.pingResult.textContent || "");
});

els.siteCheckBtn.addEventListener("click", openSiteCheckModal);
els.siteCheckModalClose.addEventListener("click", closeSiteCheckModal);
els.siteCheckModal.addEventListener("click", (event) => {
  if (event.target === els.siteCheckModal) closeSiteCheckModal();
});
els.siteCheckForm.addEventListener("submit", (event) => {
  event.preventDefault();
  runSiteCheck().catch((error) => {
    els.siteResult.textContent = error.message;
  });
});
els.siteExportBtn.addEventListener("click", () => {
  exportText("site-check-result.txt", els.siteResult.textContent || "");
});

els.languageSelect.addEventListener("change", () => {
  state.lang = els.languageSelect.value;
  localStorage.setItem("keenetic-lang", state.lang);
  applyTranslations();
  renderMetrics(state.status, state.summary);
  renderPorts();
  renderBlockedClients();
  renderClients();
});

els.refreshBtn.addEventListener("click", refresh);
els.diagnoseBtn.addEventListener("click", () => {
  runOneClickDiagnostic().catch((error) => {
    els.diagnosticResult.textContent = error.message;
    els.diagnoseBtn.disabled = false;
  });
});
els.searchInput.addEventListener("input", () => {
  state.search = els.searchInput.value;
  renderClients();
});

els.clientsBody.addEventListener("click", (event) => {
  const button = event.target.closest(".clientBlockBtn");
  if (!button) return;
  updateClientAccess(button.dataset.mac, button.dataset.blocked === "true").catch((error) => {
    setMessage(error.message);
  });
});

els.portsList.addEventListener("click", (event) => {
  const button = event.target.closest(".portPowerBtn");
  if (!button) return;
  updatePortPower(button.dataset.interfaceId, button.dataset.enabled === "true").catch((error) => {
    setMessage(error.message);
  });
});

els.blockedList.addEventListener("click", (event) => {
  const button = event.target.closest(".unblockBtn");
  if (!button) return;
  updateClientAccess(button.dataset.mac, false).catch((error) => {
    setMessage(error.message);
  });
});

els.wifiForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const password = els.wifiPasswordInput.value.trim();
  updateWifiPassword(password).catch((error) => {
    setMessage(error.message);
  });
});

els.wifiSsidBtn.addEventListener("click", () => {
  const ssid = els.wifiSsidInput.value.trim();
  updateWifiSsid(ssid).catch((error) => {
    setMessage(error.message);
  });
});

els.wifiOffBtn.addEventListener("click", () => {
  updateWifiPower(false).catch((error) => {
    setMessage(error.message);
  });
});

els.wifiOnBtn.addEventListener("click", () => {
  updateWifiPower(true).catch((error) => {
    setMessage(error.message);
  });
});

els.restartBtn.addEventListener("click", () => {
  restartRouter().catch((error) => {
    setMessage(error.message);
  });
});

els.viewScaleSelect.addEventListener("change", () => {
  state.viewScale = els.viewScaleSelect.value;
  localStorage.setItem("keenetic-view-scale", state.viewScale);
  applyViewPrefs();
});

els.sectionToggles.forEach((toggle) => {
  toggle.addEventListener("change", () => {
    state.sectionPrefs[toggle.dataset.targetPanel] = toggle.checked;
    saveSectionPrefs();
    applyViewPrefs();
  });
});

els.segments.forEach((button) => {
  button.addEventListener("click", () => {
    els.segments.forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.filter = button.dataset.filter;
    renderClients();
  });
});

applyTranslations();
applyPanelOrder();
initDraggablePanels();
applyPanelSizes();
applyAuthState();
if (state.auth?.token) refresh();
setInterval(() => {
  if (state.auth?.token) loadDashboard();
}, 5000);
