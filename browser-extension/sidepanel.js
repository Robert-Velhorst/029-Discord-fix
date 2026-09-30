const API_ORIGIN_PERMISSION = "http://127.0.0.1/*";
const NATIVE_HOST = "com.discordfix.companion";
const VIEW_TITLES = {
  Overview: "Your dashboard",
  "Important Now": "Important",
  "Needs Reply": "Needs reply",
  Conversations: "Conversations",
  Later: "Later",
  Everything: "Everything",
};
const SOURCE_STATUS_TITLES = {
  synced: "Synced",
  partial: "Partially synced",
  imported: "Imported",
  stale: "Stale",
  pending: "Waiting to sync",
  revoked: "Access revoked",
  offline: "Offline",
  error: "Error",
  unknown: "Unknown status",
};
const DEFAULT_PREFERENCES = {
  theme: "system",
  density: "comfortable",
  showCounts: true,
  showSources: false,
  textSize: 14,
  showMetadata: true,
  preset: "custom",
};

const ui = Object.fromEntries(
  [
    "connection", "connection-form", "connection-title", "dashboard-url", "dashboard",
    "preferences", "settings-toggle", "disconnect", "theme", "density", "show-counts",
    "show-sources", "counts", "count-important", "count-reply", "count-later", "search-form",
    "search", "clear-search", "view-title", "result-count", "status", "items", "sources",
    "source-count", "source-list", "refresh", "connect", "connection-error", "change-connection",
    "preset", "text-size", "show-metadata", "since-visit", "pinned-only", "show-summary",
    "saved-view", "saved-name", "save-view", "remove-view", "setup-hint", "action-status",
    "undo-action", "back-conversations", "pagination", "previous-page", "next-page", "page-label",
    "detail", "detail-content", "close-detail", "native-connect", "reset-access",
  ].map((id) => [id, document.getElementById(id)]),
);

const state = {
  baseUrl: "",
  view: "Overview",
  preferences: { ...DEFAULT_PREFERENCES },
  searchTimer: 0,
  refreshTimer: 0,
  requestId: 0,
  controller: null,
  detailController: null,
  offset: 0,
  anchor: null,
  conversation: "",
  pins: [],
  savedViews: [],
  lastVisit: "",
  visitRecorded: false,
  workflow: { enabled: false, nonce: "" },
  undo: null,
  acting: false,
  connectionEpoch: 0,
  connectionStoreQueue: Promise.resolve(),
  permissionRequest: null,
  connecting: false,
  clearing: false,
  detailId: "",
};

function normalizePreferences(value = {}) {
  return {
    theme: ["system", "dark", "light"].includes(value?.theme) ? value.theme : "system",
    density: ["comfortable", "compact"].includes(value?.density) ? value.density : "comfortable",
    showCounts: typeof value?.showCounts === "boolean" ? value.showCounts : true,
    showSources: typeof value?.showSources === "boolean" ? value.showSources : false,
    showMetadata: typeof value?.showMetadata === "boolean" ? value.showMetadata : true,
    textSize: [12, 14, 18, 22].includes(value?.textSize) ? value.textSize : 14,
    preset: ["custom", "focus", "compact", "context"].includes(value?.preset) ? value.preset : "custom",
  };
}

function normalizeDashboardUrl(value) {
  let url;
  try {
    url = new URL(value.trim());
  } catch {
    throw new Error("Enter a valid dashboard URL.");
  }
  const path = url.pathname.split("/").filter(Boolean);
  if (
    url.protocol !== "http:" ||
    url.hostname !== "127.0.0.1" ||
    !url.port ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    path.length !== 1 ||
    !/^[A-Za-z0-9_-]{20,}$/.test(path[0])
  ) {
    throw new Error("Paste the full Discord Fix link with 127.0.0.1 and its secret path.");
  }
  return `${url.origin}/${path[0]}/`;
}

function setStatus(message, kind = "info") {
  ui.status.textContent = message;
  ui.status.dataset.state = kind;
}

function applyPreferences() {
  const { theme, density, showCounts, showSources } = state.preferences;
  const resolvedTheme = theme === "system"
    ? (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark")
    : theme;
  document.documentElement.dataset.theme = resolvedTheme;
  document.documentElement.dataset.density = density;
  ui.theme.value = theme;
  ui.density.value = density;
  ui["show-counts"].checked = showCounts;
  ui["show-sources"].checked = showSources;
  ui.counts.hidden = !showCounts;
  ui.sources.hidden = !showSources || !ui["source-list"].childElementCount;
  ui["text-size"].value = String(state.preferences.textSize);
  ui["show-metadata"].checked = state.preferences.showMetadata;
  ui.preset.value = state.preferences.preset;
  document.documentElement.style.setProperty("--message-size", `${state.preferences.textSize}px`);
  document.documentElement.dataset.metadata = String(state.preferences.showMetadata);
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function safeDiscordUrl(value) {
  if (typeof value !== "string") return "";
  try {
    const url = new URL(value);
    if (url.protocol === "https:" && url.hostname === "discord.com" &&
        !url.username && !url.password && !url.port && !url.search && !url.hash &&
        /^\/channels\/\d+\/\d+\/\d+$/.test(url.pathname)) {
      return url.href;
    }
  } catch {
    return "";
  }
  return "";
}

function addTag(container, label, className) {
  const tag = document.createElement("span");
  tag.className = `tag ${className}`;
  tag.textContent = label;
  container.append(tag);
}

function renderItems(items) {
  ui.items.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No messages found in this view.";
    ui.items.append(empty);
    return;
  }

  for (const item of items.slice(0, 60)) {
    const article = document.createElement("article");
    article.className = "item";
    const heading = document.createElement("div");
    heading.className = "item-heading";
    const channel = document.createElement("strong");
    channel.className = "item-channel";
    channel.textContent = item.channel_name || "Discord conversation";
    heading.append(channel);
    const timestamp = document.createElement("time");
    timestamp.className = "item-time";
    timestamp.dateTime = typeof item.timestamp === "string" ? item.timestamp : "";
    timestamp.textContent = formatDate(item.timestamp);
    heading.append(timestamp);
    article.append(heading);

    if (item.author) {
      const author = document.createElement("span");
      author.className = "item-author";
      author.textContent = item.author_label || item.author;
      article.append(author);
    }

    const content = document.createElement("p");
    content.className = "item-content";
    content.textContent = item.deleted ? "Deleted at the source" :
      typeof item.content === "string" ? item.content : "";
    article.append(content);

    const tags = document.createElement("div");
    tags.className = "item-tags";
    if (!item.deleted) {
      if (item.state === "complete") addTag(tags, "Completed", "tag-complete");
      else if (item.state === "dismissed") addTag(tags, "Dismissed", "tag-dismissed");
      else if (item.state === "later") addTag(tags, "Later", "tag-later");
      else {
        if (item.important) addTag(tags, "Important", "tag-important");
        if (item.reply) addTag(tags, "Needs reply", "tag-reply");
      }
      const deadline = formatDate(item.deadline);
      if (deadline) addTag(tags, `Due ${deadline}`, "tag-deadline");
    }
    if (tags.childElementCount) article.append(tags);

    const link = safeDiscordUrl(item.url);
    if (link) {
      const anchor = document.createElement("a");
      anchor.className = "original-link";
      anchor.href = link;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      anchor.textContent = "Open original in Discord";
      article.append(anchor);
    }
    const context = document.createElement("button");
    context.type = "button";
    context.className = "secondary-button";
    context.textContent = "Why this appears and full context";
    context.addEventListener("click", () => loadDetail(item.id));
    article.append(context);
    ui.items.append(article);
  }
}

function renderSources(sources) {
  ui["source-list"].replaceChildren();
  for (const source of sources) {
    const row = document.createElement("li");
    row.className = "source-row";
    const name = document.createElement("span");
    name.className = "source-name";
    name.textContent = source.name || "Source";
    const status = document.createElement("span");
    status.className = "source-state";
    status.dataset.status = source.status || "unknown";
    status.textContent = Object.hasOwn(SOURCE_STATUS_TITLES, source.status)
      ? SOURCE_STATUS_TITLES[source.status] : SOURCE_STATUS_TITLES.unknown;
    const lastSync = formatDate(source.last_sync);
    if (lastSync) status.title = `Last synced ${lastSync}`;
    row.append(name, status);
    ui["source-list"].append(row);
  }
  ui["source-count"].textContent = String(sources.length);
  ui.sources.hidden = !state.preferences.showSources || sources.length === 0;
}

function updateViewControls() {
  ui["view-title"].textContent = state.conversation ? "Conversation context" : VIEW_TITLES[state.view] || VIEW_TITLES.Overview;
  ui["pinned-only"].disabled = state.view !== "Conversations";
  ui["back-conversations"].hidden = !state.conversation;
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.view === state.view));
  });
}

async function loadDashboard() {
  if (!state.baseUrl) return;
  state.detailController?.abort();
  state.detailId = "";
  ui.detail.hidden = true;
  ui["detail-content"].replaceChildren();
  ui.items.hidden = false;
  ui.pagination.hidden = true;
  state.controller?.abort();
  const controller = new AbortController();
  state.controller = controller;
  const requestId = ++state.requestId;
  const baseUrl = state.baseUrl;
  const view = state.view;
  const search = ui.search.value.trim();
  const offset = state.offset;
  const conversation = state.conversation;
  const isCurrent = () => requestId === state.requestId && baseUrl === state.baseUrl &&
    view === state.view && search === ui.search.value.trim() && offset === state.offset && conversation === state.conversation;
  const timeout = window.setTimeout(() => controller.abort(), 10000);
  ui.refresh.disabled = true;
  ui.items.replaceChildren();
  ui["result-count"].textContent = "";
  ui.items.setAttribute("aria-busy", "true");
  setStatus("Refreshing dashboard…");
  const query = new URLSearchParams({ view, q: search, offset: String(offset) });
  if (state.anchor !== null) query.set("anchor", String(state.anchor));
  if (conversation) query.set("conversation", conversation);
  if (ui["since-visit"].checked && state.lastVisit) query.set("since", state.lastVisit);
  if (ui["pinned-only"].checked && state.view === "Conversations") query.set("pins", state.pins.join(","));
  try {
    const response = await fetch(`${baseUrl}api/dashboard?${query}`, {
      cache: "no-store",
      credentials: "omit",
      redirect: "error",
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(response.status === 404
      ? "The local link has expired. Open Browserdashboard again in Discord Fix and connect with the new URL."
      : "The local Discord Fix server cannot provide the dashboard right now.");
    const data = await response.json();
    if (!isCurrent()) return;
    if (!data || !Array.isArray(data.items) || !data.counts || !Array.isArray(data.sources)) {
      throw new Error("The local server returned an unrecognized Discord Fix dashboard.");
    }
    state.workflow = data.workflow || { enabled: false, nonce: "" };
    if (state.view === "Conversations" && !state.conversation && Array.isArray(data.groups)) renderGroups(data.groups);
    else renderItems(data.items);
    renderSources(data.sources);
    ui["count-important"].textContent = String(Number(data.counts.important) || 0);
    ui["count-reply"].textContent = String(Number(data.counts.reply) || 0);
    ui["count-later"].textContent = String(Number(data.counts.later) || 0);
    const total = data.pagination?.total ?? data.items.length;
    const noun = state.view === "Conversations" && !state.conversation ? (total === 1 ? "conversation" : "conversations") : (total === 1 ? "message" : "messages");
    ui["result-count"].textContent = `${total} ${noun}`;
    if (data.pagination) {
      state.offset = data.pagination.offset;
      state.anchor = data.pagination.anchor;
      ui.pagination.hidden = total <= data.pagination.limit;
      ui["previous-page"].disabled = state.offset === 0;
      ui["next-page"].disabled = !data.pagination.has_more;
      ui["page-label"].textContent = `Page ${Math.floor(state.offset / data.pagination.limit) + 1} of ${Math.max(1, Math.ceil(total / data.pagination.limit))}`;
    }
    ui["setup-hint"].hidden = data.sources.length > 0;
    if (!state.visitRecorded) {
      state.visitRecorded = true;
      chrome.storage.local.set({ lastVisit: new Date().toISOString() }).catch(() => {
        ui["action-status"].textContent = "Could not save your visit time. Since last visit may be unavailable next time.";
      });
    }
    const generated = formatDate(data.generated_at);
    setStatus((generated ? `Updated ${generated}` : "Dashboard updated.") + (data.new_items ? " New messages are available; refresh to include them." : ""));
  } catch (error) {
    if (!isCurrent()) return;
    ui["source-list"].replaceChildren();
    ui.sources.hidden = true;
    for (const id of ["count-important", "count-reply", "count-later"]) ui[id].textContent = "—";
    const message = controller.signal.aborted
      ? "The local Discord Fix server did not respond in time."
      : error.name === "TypeError"
        ? "No connection. Check that Discord Fix is open and your local link is correct."
        : error.name === "SyntaxError"
          ? "The local server returned an unrecognized Discord Fix dashboard."
          : error.message || "Could not load the dashboard.";
    setStatus(message, "error");
  } finally {
    window.clearTimeout(timeout);
    if (requestId === state.requestId) {
      state.controller = null;
      ui.refresh.disabled = false;
      ui.items.setAttribute("aria-busy", "false");
    }
  }
}

function showConnected() {
  ui.connection.hidden = true;
  ui.dashboard.hidden = false;
  ui["settings-toggle"].hidden = false;
  ui.refresh.hidden = false;
  updateViewControls();
  applyPreferences();
  loadDashboard();
}

async function initialize() {
  const epoch = state.connectionEpoch;
  state.refreshTimer = window.setInterval(() => { if (ui.detail.hidden && !state.acting) loadDashboard(); }, 30000);
  const stored = await chrome.storage.local.get([
    "dashboardUrl", "preferences", "view", "pins", "savedViews", "lastVisit",
  ]);
  if (epoch !== state.connectionEpoch) return;
  state.preferences = normalizePreferences(stored.preferences);
  state.view = Object.hasOwn(VIEW_TITLES, stored.view) ? stored.view : "Overview";
  state.pins = Array.isArray(stored.pins) ? stored.pins.filter((id) => typeof id === "string" && /^[a-f0-9]{64}$/.test(id)).slice(0, 100) : [];
  state.savedViews = Array.isArray(stored.savedViews) ? stored.savedViews.filter((v) => typeof v?.name === "string" && v.name.length <= 50 && Object.hasOwn(VIEW_TITLES, v.view) && typeof v.q === "string" && v.q.length <= 160).slice(0, 20) : [];
  state.lastVisit = typeof stored.lastVisit === "string" && /(?:Z|[+-]\d{2}:\d{2})$/.test(stored.lastVisit) && Number.isFinite(Date.parse(stored.lastVisit)) && Date.parse(stored.lastVisit) <= Date.now() ? stored.lastVisit : "";
  ui["since-visit"].disabled = !state.lastVisit;
  ui["since-visit"].title = state.lastVisit ? `Since ${formatDate(state.lastVisit)}` : "Available after your next visit";
  renderSavedViews();
  applyPreferences();
  updateViewControls();
  const savedUrl = typeof stored.dashboardUrl === "string" ? stored.dashboardUrl : "";
  if (savedUrl) {
    try {
      state.baseUrl = normalizeDashboardUrl(savedUrl);
      const granted = await chrome.permissions.contains({ origins: [API_ORIGIN_PERMISSION] });
      if (epoch !== state.connectionEpoch) return;
      if (granted) {
        showConnected();
        return;
      }
      ui["dashboard-url"].value = state.baseUrl;
      state.baseUrl = "";
      setStatus("Local access was revoked. Connect again to grant access.");
      ui.status.dataset.state = "error";
    } catch {
      state.baseUrl = "";
      await chrome.storage.local.remove("dashboardUrl");
    }
  }
  ui.connection.hidden = false;
  ui.dashboard.hidden = true;
  ui["settings-toggle"].hidden = true;
  ui.refresh.hidden = true;
  if (ui.status.dataset.state !== "error") setStatus("Not connected to Discord Fix.");
}

function connecting(disabled) {
  state.connecting = disabled;
  ui.connect.disabled = disabled;
  ui["native-connect"].disabled = disabled;
}

function requestAccess(request) {
  const pending = chrome.permissions.request(request);
  state.permissionRequest = pending;
  return pending.finally(() => {
    if (state.permissionRequest === pending) state.permissionRequest = null;
  });
}

function storeConnection(operation) {
  const next = state.connectionStoreQueue.then(operation);
  state.connectionStoreQueue = next.catch(() => {});
  return next;
}

async function finishConnection(baseUrl, epoch) {
  if (epoch !== state.connectionEpoch) return;
  try {
    await storeConnection(async () => {
      if (epoch === state.connectionEpoch) await chrome.storage.local.set({ dashboardUrl: baseUrl });
    });
  } catch {
    throw new Error("Could not save the connection in this browser. Try connecting again.");
  }
  if (epoch !== state.connectionEpoch) return;
  state.baseUrl = baseUrl;
  showConnected();
  ui.search.focus();
}

function connectionError(message) {
  ui["connection-error"].textContent = message;
  ui["connection-error"].hidden = false;
}

ui["connection-form"].addEventListener("submit", async (event) => {
  event.preventDefault();
  if (ui.connect.disabled) return;
  connecting(true);
  const epoch = ++state.connectionEpoch;
  setStatus("Connecting to Discord Fix…");
  ui["connection-error"].hidden = true;
  ui["dashboard-url"].removeAttribute("aria-invalid");
  const input = ui["dashboard-url"].value;
  let validated = false;
  try {
    const baseUrl = normalizeDashboardUrl(input);
    validated = true;
    let granted;
    try {
      granted = await requestAccess({ origins: [API_ORIGIN_PERMISSION] });
    } catch {
      throw new Error("The browser could not request access to the local dashboard.");
    }
    if (epoch !== state.connectionEpoch) return;
    if (!granted) throw new Error("Access to the local Discord Fix server was not granted.");
    await finishConnection(baseUrl, epoch);
  } catch (error) {
    if (epoch !== state.connectionEpoch) return;
    setStatus("Not connected to Discord Fix.", "error");
    connectionError(error.message || "Could not validate the URL.");
    if (!validated) ui["dashboard-url"].setAttribute("aria-invalid", "true");
    ui["dashboard-url"].focus();
  } finally {
    if (epoch === state.connectionEpoch) connecting(false);
  }
});

function nativePairing() {
  let timeout;
  return Promise.race([
    chrome.runtime.sendNativeMessage(NATIVE_HOST, { command: "pair", protocol: 1 }),
    new Promise((_, reject) => {
      timeout = window.setTimeout(() => reject(new Error("Pairing timed out.")), 15000);
    }),
  ]).finally(() => window.clearTimeout(timeout));
}

ui["native-connect"].addEventListener("click", async () => {
  if (ui["native-connect"].disabled) return;
  connecting(true);
  const epoch = ++state.connectionEpoch;
  setStatus("Pairing with desktop app…");
  ui["connection-error"].hidden = true;
  try {
    // Request directly from this click; no startup discovery or automatic grant.
    let granted;
    try {
      granted = await requestAccess({ permissions: ["nativeMessaging"], origins: [API_ORIGIN_PERMISSION] });
    } catch {
      throw new Error("The browser could not request local pairing access. Use the manual connection below.");
    }
    if (epoch !== state.connectionEpoch) return;
    if (!granted) throw new Error("Local pairing access was not granted. You can paste the private address below instead.");
    let reply;
    try { reply = await nativePairing(); } catch {
      throw new Error("Could not reach the Windows pairing helper. Check its installation, keep Browserdashboard open, or paste the private address below.");
    }
    if (epoch !== state.connectionEpoch) return;
    if (reply?.ok !== true || reply?.protocol !== 1 || typeof reply?.url !== "string") {
      throw new Error("The desktop session is unavailable. Open Browserdashboard again, check the helper registration, or paste its private address below.");
    }
    let baseUrl;
    try { baseUrl = normalizeDashboardUrl(reply.url); } catch {
      throw new Error("The helper returned an invalid local address. Use the private address from the desktop app instead.");
    }
    await finishConnection(baseUrl, epoch);
  } catch (error) {
    if (epoch === state.connectionEpoch) {
      setStatus("Not connected to Discord Fix.", "error");
      connectionError(error.message);
    }
  } finally {
    if (epoch === state.connectionEpoch) connecting(false);
  }
});

ui["settings-toggle"].addEventListener("click", () => {
  const expanded = ui["settings-toggle"].getAttribute("aria-expanded") === "true";
  ui["settings-toggle"].setAttribute("aria-expanded", String(!expanded));
  ui.preferences.hidden = expanded;
});

ui["refresh"].addEventListener("click", () => { resetPage(); loadDashboard(); });

document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", async () => {
    state.view = button.dataset.view;
    state.conversation = "";
    ui["pinned-only"].checked = false;
    resetPage();
    updateViewControls();
    loadDashboard();
    try {
      await chrome.storage.local.set({ view: state.view });
    } catch {
      setStatus("This view could not be saved for next time.", "error");
    }
  });
});

ui["search-form"].addEventListener("submit", (event) => {
  event.preventDefault();
  resetPage();
  loadDashboard();
});

ui.search.addEventListener("input", () => {
  ui["clear-search"].hidden = !ui.search.value;
  resetPage();
  window.clearTimeout(state.searchTimer);
  state.searchTimer = window.setTimeout(loadDashboard, 250);
});

ui["clear-search"].addEventListener("click", () => {
  ui.search.value = "";
  resetPage();
  ui["clear-search"].hidden = true;
  loadDashboard();
  ui.search.focus();
});

async function savePreferences() {
  state.preferences = {
    theme: ui.theme.value,
    density: ui.density.value,
    showCounts: ui["show-counts"].checked,
    showSources: ui["show-sources"].checked,
    textSize: Number(ui["text-size"].value),
    showMetadata: ui["show-metadata"].checked,
    preset: ui.preset.value,
  };
  applyPreferences();
  try {
    await chrome.storage.local.set({ preferences: state.preferences });
  } catch {
    setStatus("Display settings apply now, but could not be saved for next time.", "error");
  }
}

[ui.theme, ui.density, ui["show-counts"], ui["show-sources"], ui["text-size"], ui["show-metadata"]].forEach((control) => {
  control.addEventListener("change", () => { ui.preset.value = "custom"; savePreferences(); });
});

function clearConnectionUI() {
  ++state.connectionEpoch;
  ++state.requestId;
  state.controller?.abort();
  state.controller = null;
  state.detailController?.abort();
  state.detailId = "";
  state.workflow = { enabled: false, nonce: "" };
  state.undo = null;
  state.lastVisit = "";
  state.visitRecorded = false;
  state.conversation = "";
  resetPage();
  ui.detail.hidden = true;
  ui["detail-content"].replaceChildren();
  ui["undo-action"].hidden = true;
  ui["action-status"].textContent = "";
  ui["since-visit"].checked = false;
  ui["since-visit"].disabled = true;
  state.baseUrl = "";
  window.clearTimeout(state.searchTimer);
  ui.items.replaceChildren();
  ui.items.setAttribute("aria-busy", "false");
  ui["source-list"].replaceChildren();
  ui.sources.hidden = true;
  ui["source-count"].textContent = "";
  ui["result-count"].textContent = "";
  for (const id of ["count-important", "count-reply", "count-later"]) ui[id].textContent = "0";
  ui.search.value = "";
  ui["clear-search"].hidden = true;
  ui.preferences.hidden = true;
  ui["settings-toggle"].setAttribute("aria-expanded", "false");
  ui["settings-toggle"].hidden = true;
  ui.refresh.hidden = true;
  ui["connection-error"].hidden = true;
  ui["dashboard-url"].removeAttribute("aria-invalid");
  ui.connection.hidden = false;
  ui.dashboard.hidden = true;
  ui["dashboard-url"].value = "";
  ui["dashboard-url"].focus();
  ui.refresh.disabled = false;
}

async function disconnect() {
  if (state.clearing) return;
  state.clearing = true;
  ui["reset-access"].disabled = true;
  const pendingPermission = state.permissionRequest;
  clearConnectionUI();
  const epoch = state.connectionEpoch;
  connecting(true);
  setStatus("Clearing connection…");
  // A still-open grant prompt must settle before revocation, so a late grant
  // cannot restore access after Clear connection has completed.
  if (pendingPermission) await pendingPermission.catch(() => {});
  const results = await Promise.allSettled([
    storeConnection(() => chrome.storage.local.remove("dashboardUrl")),
    chrome.permissions.remove({ permissions: ["nativeMessaging"], origins: [API_ORIGIN_PERMISSION] }),
  ]);
  state.clearing = false;
  ui["reset-access"].disabled = false;
  if (epoch !== state.connectionEpoch) return;
  connecting(false);
  if (results.some((result) => result.status === "rejected" || result.value === false)) {
    setStatus("Disconnected for this session. The browser could not clear all saved access. " +
      "Remove the extension's local-site access in browser settings before closing this panel.", "error");
  } else setStatus("Connection cleared. Paste a new dashboard URL to reconnect.");
}

ui.disconnect.addEventListener("click", disconnect);
ui["change-connection"].addEventListener("click", disconnect);
ui["reset-access"].addEventListener("click", disconnect);

chrome.permissions.onRemoved.addListener((removed) => {
  if (state.clearing || (!state.baseUrl && !state.connecting) || !removed.origins?.includes(API_ORIGIN_PERMISSION)) return;
  clearConnectionUI();
  connecting(false);
  setStatus("Local access was revoked. Connect again to grant access.", "error");
});

chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== "local" || !state.baseUrl || !changes.dashboardUrl || changes.dashboardUrl.newValue === state.baseUrl) return;
  clearConnectionUI();
  connecting(false);
  setStatus("The saved connection changed in another panel. Connect again to continue.", "error");
});

function resetPage() {
  state.offset = 0;
  state.anchor = null;
}

function node(tag, text, className = "") {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  element.className = className;
  return element;
}

function button(text, action) {
  const element = node("button", text, "secondary-button");
  element.type = "button";
  element.addEventListener("click", action);
  return element;
}

function renderGroups(groups) {
  ui.items.replaceChildren();
  if (!groups.length) ui.items.append(node("p", "No matching conversations. Try another search or clear the pinned filter.", "empty-state"));
  for (const group of groups) {
    const card = node("article", undefined, "item");
    card.append(node("h2", group.channel_name));
    card.append(node("p", `${group.count} ${group.count === 1 ? "message" : "messages"} · ${group.open_replies} open ${group.open_replies === 1 ? "follow-up" : "follow-ups"}`));
    const kind = { thread: "Thread", reply: "Linked replies", conversation: "Conversation", channel: "Channel grouping; separate topics may be present" };
    card.append(node("p", kind[group.kind] || "Conversation"));
    card.append(node("p", (group.participants || []).join(", ")));
    card.append(button("Open conversation", () => {
      state.conversation = group.id; resetPage(); updateViewControls(); loadDashboard();
    }));
    card.append(button(state.pins.includes(group.id) ? "Unpin conversation" : "Pin conversation", async () => {
      state.pins = state.pins.includes(group.id) ? state.pins.filter((id) => id !== group.id) : [...state.pins.slice(-99), group.id];
      try { await chrome.storage.local.set({ pins: state.pins }); }
      catch { ui["action-status"].textContent = "Could not save pinned conversations for next time."; }
      loadDashboard();
    }));
    ui.items.append(card);
  }
}

async function localGet(resource, controller) {
  const response = await fetch(`${state.baseUrl}api/${resource}`, {
    cache: "no-store", credentials: "omit", redirect: "error", signal: controller.signal,
  });
  if (!response.ok) throw new Error("This local context is unavailable. Refresh or reconnect.");
  return response.json();
}

function openDetail(id) {
  state.detailController?.abort();
  const controller = new AbortController();
  state.detailController = controller;
  state.controller?.abort(); ++state.requestId;
  ui.refresh.disabled = false; state.detailId = id;
  ui.detail.hidden = false; ui.items.hidden = true; ui.pagination.hidden = true;
  ui["detail-content"].replaceChildren(node("p", "Loading local context…"));
  return controller;
}

async function loadDetail(ident) {
  if (!state.baseUrl) return;
  const baseUrl = state.baseUrl;
  const controller = openDetail(ident);
  const timeout = window.setTimeout(() => controller.abort(), 10000);
  try {
    const item = await localGet(`message?${new URLSearchParams({ id: ident })}`, controller);
    if (baseUrl !== state.baseUrl || state.detailController !== controller || controller.signal.aborted) return;
    const content = ui["detail-content"];
    content.replaceChildren();
    const title = node("h2", item.channel_name || "Message context"); title.tabIndex = -1;
    content.append(title, node("p", `${item.author_label || item.author || "Unknown author"} · ${formatDate(item.timestamp)}`));
    content.append(node("p", item.deleted ? "Deleted at the source" : item.content, "full-content"));
    if (item.content_truncated) content.append(node("p", "This unusually large message is shortened; open the original for more."));
    content.append(node("h3", "Why this appears"));
    const reasons = node("ul");
    for (const reason of item.reasons || []) reasons.append(node("li", reason.text));
    content.append(reasons, node("h3", "Source and coverage"));
    const source = item.source || {};
    content.append(node("p", `${source.name || "Unavailable source"} · ${Object.hasOwn(SOURCE_STATUS_TITLES, source.status) ? SOURCE_STATUS_TITLES[source.status] : "Unknown status"}`));
    content.append(node("p", source.coverage || "Coverage unavailable."));
    content.append(node("p", `Server ID: ${item.guild || "Not provided"} · Channel ID: ${item.channel || "Not provided"}`));
    content.append(node("p", `Imported or received: ${formatDate(item.imported_at)} · Last source sync: ${formatDate(source.last_sync) || "Not recorded"}`));
    if (item.until) content.append(node("p", `Postponed until ${formatDate(item.until)}`));
    const link = safeDiscordUrl(item.url);
    if (link) {
      const anchor = node("a", "Open original in Discord", "original-link");
      anchor.href = link; anchor.target = "_blank"; anchor.rel = "noopener noreferrer"; content.append(anchor);
    }
    if (state.workflow.enabled && !item.deleted) {
      content.append(node("h3", "Local follow-up"), node("p", "These actions update Discord Fix only. They do not send or change Discord messages."));
      const actions = node("div", undefined, "workflow-actions");
      for (const [label, action] of [[item.state === "open" ? "Complete" : "Reopen", item.state === "open" ? "complete" : "reopen"], ["Dismiss", "dismiss"], [item.important ? "Remove priority" : "Mark important", "important"], [item.reply ? "No reply needed" : "Needs reply", "reply"]]) actions.append(button(label, () => sendAction(item, action)));
      const label = node("label", "Postpone for "); const duration = node("select");
      for (const [minutes, text] of [[60, "1 hour"], [1440, "24 hours"], [10080, "1 week"]]) {
        const option = node("option", text); option.value = String(minutes); duration.append(option);
      }
      label.append(duration); actions.append(label, button("Snooze", () => sendAction(item, "later", { minutes: Number(duration.value) }))); content.append(actions);
    }
    content.append(node("p", "Saved summaries follow the source's original conversation and channel boundaries; other topics may be included."));
    content.append(button("Read saved source conversation summary", () => loadSummary("conversation", item.conversation || item.channel)));
    content.append(button("Read saved channel summary", () => loadSummary("channel", item.parent_channel || item.channel)));
    if (item.guild && item.guild !== "@me") content.append(button("Read saved server summary", () => loadSummary("server", item.guild)));
    title.focus();
  } catch {
    if (baseUrl === state.baseUrl && state.detailController === controller) ui["detail-content"].replaceChildren(node("p", controller.signal.aborted ? "Context request timed out. Try again." : "Could not load this local context. Refresh or reconnect."));
  } finally { window.clearTimeout(timeout); }
}

async function sendAction(item, action, extra = {}) {
  if (state.acting || !state.baseUrl || !state.workflow.enabled) return;
  state.acting = true;
  const baseUrl = state.baseUrl;
  const epoch = state.connectionEpoch;
  const isCurrent = () => baseUrl === state.baseUrl && epoch === state.connectionEpoch;
  ui["action-status"].textContent = "Saving local follow-up…";
  const controller = new AbortController(); const timeout = window.setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch(`${baseUrl}api/workflow`, {
      method: "POST", credentials: "omit", redirect: "error", cache: "no-store",
      headers: { "Content-Type": "application/json", "X-Discord-Fix-Nonce": state.workflow.nonce },
      body: JSON.stringify({ id: item.id, revision: item.revision, action, ...extra }), signal: controller.signal,
    });
    if (!isCurrent()) return;
    if (!response.ok) throw new Error(response.status === 409 ? "This item changed. Refresh before trying again." : "Could not confirm the action. Refresh and check its state before retrying.");
    const result = await response.json();
    if (!isCurrent()) return;
    state.undo = result.undo ? result : null; ui["undo-action"].hidden = !state.undo;
    ui["action-status"].textContent = action === "undo" ? "Local action undone." : "Local follow-up saved. You can undo this action.";
    resetPage(); await loadDashboard();
  } catch (error) {
    if (isCurrent()) ui["action-status"].textContent = error.name === "Error" ? error.message : "Could not confirm the action. Refresh and check its state before retrying.";
  } finally { window.clearTimeout(timeout); state.acting = false; }
}

async function loadSummary(scope = "personal", target = "*", offset = 0) {
  if (!state.baseUrl) return;
  const baseUrl = state.baseUrl; const controller = openDetail("summary");
  const timeout = window.setTimeout(() => controller.abort(), 10000);
  try {
    const data = await localGet(`summaries?${new URLSearchParams({ scope, target, offset: String(offset) })}`, controller);
    if (baseUrl !== state.baseUrl || controller !== state.detailController || controller.signal.aborted) return;
    const content = ui["detail-content"]; const title = node("h2", "Saved context summary"); title.tabIndex = -1;
    content.replaceChildren(title);
    if (!data.available) content.append(node("p", data.needs_refresh ? "This summary needs a refresh after its sources changed. Refresh summaries in the desktop app." : "No saved summary yet. Generate it in the desktop app; local extraction works without an AI provider."));
    else {
      content.append(node("p", `Generated ${formatDate(data.generated_at)} · ${data.scope}`), node("p", data.coverage));
      if (data.correction) content.append(node("p", `Your correction: ${data.correction}`));
      for (const entry of data.entries) {
        const categories = { topics: "Topics", facts: "Source statements", decisions: "Possible decisions", questions: "Questions", actions: "Possible actions", uncertainty: "Uncertainty" };
        const block = node("article", undefined, "item"); block.append(node("h3", categories[entry.category] || "Context"), node("p", entry.text), node("p", entry.basis));
        for (const citation of entry.citations) block.append(button("Inspect cited message", () => loadDetail(citation.id)), node("blockquote", citation.quote));
        content.append(block);
      }
      if (offset > 0) content.append(button("Previous summary entries", () => loadSummary(scope, target, Math.max(0, offset - 30))));
      if (data.has_more) content.append(button("More summary entries", () => loadSummary(scope, target, offset + 30)));
    }
    title.focus();
  } catch {
    if (baseUrl === state.baseUrl && controller === state.detailController) ui["detail-content"].replaceChildren(node("p", "Could not load the saved summary. Refresh or reconnect."));
  } finally { window.clearTimeout(timeout); }
}

function renderSavedViews() {
  const placeholder = node("option", "Choose a view"); placeholder.value = "";
  ui["saved-view"].replaceChildren(placeholder);
  state.savedViews.forEach((view, index) => { const option = node("option", view.name); option.value = String(index); ui["saved-view"].append(option); });
}

ui["save-view"].addEventListener("click", async () => {
  const name = ui["saved-name"].value.trim();
  if (!name) { ui["action-status"].textContent = "Enter a name for this view."; ui["saved-name"].focus(); return; }
  const view = { name: name.slice(0, 50), view: state.view, q: ui.search.value.slice(0, 160) };
  state.savedViews = [...state.savedViews.filter((v) => v.name !== view.name).slice(-19), view];
  try { await chrome.storage.local.set({ savedViews: state.savedViews }); renderSavedViews(); ui["action-status"].textContent = "View saved on this device."; }
  catch { ui["action-status"].textContent = "Could not save this view."; }
});
ui["saved-view"].addEventListener("change", () => {
  if (ui["saved-view"].value === "") return;
  const view = state.savedViews[Number(ui["saved-view"].value)]; if (!view) return;
  state.view = view.view; state.conversation = ""; ui.search.value = view.q;
  ui["clear-search"].hidden = !view.q; ui["pinned-only"].checked = false;
  resetPage(); updateViewControls(); loadDashboard();
});
ui["remove-view"].addEventListener("click", async () => {
  if (ui["saved-view"].value === "") return;
  state.savedViews.splice(Number(ui["saved-view"].value), 1);
  try { await chrome.storage.local.set({ savedViews: state.savedViews }); renderSavedViews(); ui["action-status"].textContent = "Saved view removed."; }
  catch { ui["action-status"].textContent = "Could not remove the saved view from storage."; }
});
ui.preset.addEventListener("change", () => {
  const presets = { focus: { density: "comfortable", showCounts: false, showSources: false, showMetadata: false, textSize: 18 }, compact: { density: "compact", showCounts: true, showSources: false, showMetadata: true, textSize: 12 }, context: { density: "comfortable", showCounts: true, showSources: true, showMetadata: true, textSize: 14 } };
  if (Object.hasOwn(presets, ui.preset.value)) state.preferences = { ...state.preferences, ...presets[ui.preset.value], preset: ui.preset.value };
  applyPreferences(); savePreferences();
});
ui["previous-page"].addEventListener("click", () => { state.offset = Math.max(0, state.offset - 60); loadDashboard(); });
ui["next-page"].addEventListener("click", () => { state.offset += 60; loadDashboard(); });
ui["close-detail"].addEventListener("click", () => { state.detailController?.abort(); loadDashboard(); ui.search.focus(); });
ui["show-summary"].addEventListener("click", () => loadSummary());
ui["since-visit"].addEventListener("change", () => { resetPage(); loadDashboard(); });
ui["pinned-only"].addEventListener("change", () => { resetPage(); loadDashboard(); });
ui["back-conversations"].addEventListener("click", () => { state.conversation = ""; resetPage(); updateViewControls(); loadDashboard(); });
ui["undo-action"].addEventListener("click", () => { if (state.undo) sendAction(state.undo, "undo", { undo: state.undo.undo }); });

matchMedia("(prefers-color-scheme: light)").addEventListener("change", () => {
  if (state.preferences.theme === "system") applyPreferences();
});

initialize().catch(() => {
  state.baseUrl = "";
  ui.connection.hidden = false;
  ui.dashboard.hidden = true;
  setStatus("Could not read browser extension settings.", "error");
}).finally(() => {
  if (!state.clearing) {
    connecting(false);
    ui["reset-access"].disabled = false;
  }
});
