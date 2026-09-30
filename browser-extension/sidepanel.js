const API_ORIGIN_PERMISSION = "http://127.0.0.1/*";
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
};

const ui = Object.fromEntries(
  [
    "connection", "connection-form", "connection-title", "dashboard-url", "dashboard",
    "preferences", "settings-toggle", "disconnect", "theme", "density", "show-counts",
    "show-sources", "counts", "count-important", "count-reply", "count-later", "search-form",
    "search", "clear-search", "view-title", "result-count", "status", "items", "sources",
    "source-count", "source-list", "refresh", "connect", "connection-error", "change-connection",
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
};

function normalizePreferences(value = {}) {
  return {
    theme: ["system", "dark", "light"].includes(value?.theme) ? value.theme : "system",
    density: ["comfortable", "compact"].includes(value?.density) ? value.density : "comfortable",
    showCounts: typeof value?.showCounts === "boolean" ? value.showCounts : true,
    showSources: typeof value?.showSources === "boolean" ? value.showSources : false,
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
      author.textContent = item.author;
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
  ui["view-title"].textContent = VIEW_TITLES[state.view] || VIEW_TITLES.Overview;
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.view === state.view));
  });
}

async function loadDashboard() {
  if (!state.baseUrl) return;
  state.controller?.abort();
  const controller = new AbortController();
  state.controller = controller;
  const requestId = ++state.requestId;
  const baseUrl = state.baseUrl;
  const view = state.view;
  const search = ui.search.value.trim();
  const isCurrent = () => requestId === state.requestId && baseUrl === state.baseUrl &&
    view === state.view && search === ui.search.value.trim();
  const timeout = window.setTimeout(() => controller.abort(), 10000);
  ui.refresh.disabled = true;
  ui.items.replaceChildren();
  ui["result-count"].textContent = "";
  ui.items.setAttribute("aria-busy", "true");
  setStatus("Refreshing dashboard…");
  const query = new URLSearchParams({ view, q: search });
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
    renderItems(data.items);
    renderSources(data.sources);
    ui["count-important"].textContent = String(Number(data.counts.important) || 0);
    ui["count-reply"].textContent = String(Number(data.counts.reply) || 0);
    ui["count-later"].textContent = String(Number(data.counts.later) || 0);
    const total = Array.isArray(data.items) ? data.items.length : 0;
    ui["result-count"].textContent = total === 60 ? "Showing first 60 messages" :
      `${total} ${total === 1 ? "message" : "messages"}`;
    const generated = formatDate(data.generated_at);
    setStatus(generated ? `Updated ${generated}` : "Dashboard updated.");
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
  state.refreshTimer = window.setInterval(loadDashboard, 30000);
  const stored = await chrome.storage.local.get([
    "dashboardUrl", "preferences", "view",
  ]);
  state.preferences = normalizePreferences(stored.preferences);
  state.view = Object.hasOwn(VIEW_TITLES, stored.view) ? stored.view : "Overview";
  applyPreferences();
  updateViewControls();
  const savedUrl = typeof stored.dashboardUrl === "string" ? stored.dashboardUrl : "";
  if (savedUrl) {
    try {
      state.baseUrl = normalizeDashboardUrl(savedUrl);
      const granted = await chrome.permissions.contains({ origins: [API_ORIGIN_PERMISSION] });
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

ui["connection-form"].addEventListener("submit", async (event) => {
  event.preventDefault();
  if (ui.connect.disabled) return;
  ui.connect.disabled = true;
  ui["connection-error"].hidden = true;
  ui["dashboard-url"].removeAttribute("aria-invalid");
  const input = ui["dashboard-url"].value;
  let validated = false;
  try {
    const baseUrl = normalizeDashboardUrl(input);
    validated = true;
    let granted;
    try {
      granted = await chrome.permissions.request({ origins: [API_ORIGIN_PERMISSION] });
    } catch {
      throw new Error("The browser could not request access to the local dashboard.");
    }
    if (!granted) throw new Error("Access to the local Discord Fix server was not granted.");
    try {
      await chrome.storage.local.set({ dashboardUrl: baseUrl });
    } catch {
      throw new Error("Could not save the connection in this browser. Try connecting again.");
    }
    state.baseUrl = baseUrl;
    showConnected();
    ui.search.focus();
  } catch (error) {
    const paragraph = ui["connection-error"];
    paragraph.textContent = error.message || "Could not validate the URL.";
    paragraph.hidden = false;
    if (!validated) ui["dashboard-url"].setAttribute("aria-invalid", "true");
    ui["dashboard-url"].focus();
  } finally {
    ui.connect.disabled = false;
  }
});

ui["settings-toggle"].addEventListener("click", () => {
  const expanded = ui["settings-toggle"].getAttribute("aria-expanded") === "true";
  ui["settings-toggle"].setAttribute("aria-expanded", String(!expanded));
  ui.preferences.hidden = expanded;
});

ui["refresh"].addEventListener("click", loadDashboard);

document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", async () => {
    state.view = button.dataset.view;
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
  loadDashboard();
});

ui.search.addEventListener("input", () => {
  ui["clear-search"].hidden = !ui.search.value;
  window.clearTimeout(state.searchTimer);
  state.searchTimer = window.setTimeout(loadDashboard, 250);
});

ui["clear-search"].addEventListener("click", () => {
  ui.search.value = "";
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
  };
  applyPreferences();
  try {
    await chrome.storage.local.set({ preferences: state.preferences });
  } catch {
    setStatus("Display settings apply now, but could not be saved for next time.", "error");
  }
}

[ui.theme, ui.density, ui["show-counts"], ui["show-sources"]].forEach((control) => {
  control.addEventListener("change", savePreferences);
});

async function disconnect() {
  ++state.requestId;
  state.controller?.abort();
  state.controller = null;
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
  ui.connect.disabled = true;
  setStatus("Clearing connection…");
  const results = await Promise.allSettled([
    chrome.storage.local.remove("dashboardUrl"),
    chrome.permissions.remove({ origins: [API_ORIGIN_PERMISSION] }),
  ]);
  ui.connect.disabled = false;
  if (results.some((result) => result.status === "rejected")) {
    setStatus("Disconnected for this session. The browser could not clear all saved access. " +
      "Remove the extension's local-site access in browser settings before closing this panel.", "error");
  } else setStatus("Connection cleared. Paste a new dashboard URL to reconnect.");
}

ui.disconnect.addEventListener("click", disconnect);
ui["change-connection"].addEventListener("click", disconnect);

matchMedia("(prefers-color-scheme: light)").addEventListener("change", () => {
  if (state.preferences.theme === "system") applyPreferences();
});

initialize().catch(() => {
  state.baseUrl = "";
  ui.connection.hidden = false;
  ui.dashboard.hidden = true;
  setStatus("Could not read browser extension settings.", "error");
}).finally(() => { ui.connect.disabled = false; });
