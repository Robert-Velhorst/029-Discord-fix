const API_ORIGIN_PERMISSION = "http://127.0.0.1/*";
const VIEW_TITLES = {
  Overview: "Jouw overzicht",
  "Important Now": "Nu belangrijk",
  "Needs Reply": "Opvolgen",
  Conversations: "Gesprekken",
  Later: "Later",
  Everything: "Alles",
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
    "source-count", "source-list", "refresh",
  ].map((id) => [id, document.getElementById(id)]),
);

const state = {
  baseUrl: "",
  view: "Overview",
  preferences: { ...DEFAULT_PREFERENCES },
  searchTimer: 0,
  refreshTimer: 0,
  loading: false,
  refreshPending: false,
};

function normalizeDashboardUrl(value) {
  const url = new URL(value.trim());
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
    throw new Error("Plak de volledige Discord Fix-link met 127.0.0.1 en de geheime padcode.");
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
  ui.sources.hidden = !showSources;
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("nl-NL", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function safeDiscordUrl(value) {
  if (typeof value !== "string") return "";
  try {
    const url = new URL(value);
    if (url.protocol === "https:" && url.hostname === "discord.com" && url.pathname.startsWith("/channels/")) {
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
    empty.textContent = "Geen berichten gevonden in deze weergave.";
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
    channel.textContent = item.channel_name || "Discord-gesprek";
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
    content.textContent = typeof item.content === "string" ? item.content : "";
    article.append(content);

    const tags = document.createElement("div");
    tags.className = "item-tags";
    if (item.important) addTag(tags, "Belangrijk", "tag-important");
    if (item.reply) addTag(tags, "Opvolgen", "tag-reply");
    if (item.state === "later") addTag(tags, "Later", "tag-later");
    if (tags.childElementCount) article.append(tags);

    const link = safeDiscordUrl(item.url);
    if (link) {
      const anchor = document.createElement("a");
      anchor.className = "original-link";
      anchor.href = link;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      anchor.textContent = "Open origineel in Discord";
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
    name.textContent = source.name || "Bron";
    const status = document.createElement("span");
    status.className = "source-state";
    status.dataset.status = source.status || "unknown";
    status.textContent = source.label || "Status onbekend";
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
  if (state.loading) {
    state.refreshPending = true;
    return;
  }
  state.loading = true;
  ui.refresh.disabled = true;
  setStatus("Overzicht vernieuwen…");
  const query = new URLSearchParams({ view: state.view, q: ui.search.value.trim() });
  try {
    const response = await fetch(`${state.baseUrl}api/dashboard?${query}`, {
      cache: "no-store",
      credentials: "omit",
      redirect: "error",
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) throw new Error(response.status === 404
      ? "De lokale koppeling is verlopen. Open Browserdashboard opnieuw en verbind met de nieuwe URL."
      : "De lokale Discord Fix-server kan het overzicht nu niet leveren.");
    const data = await response.json();
    if (!data || !Array.isArray(data.items) || !data.counts || !Array.isArray(data.sources)) {
      throw new Error("De lokale server gaf geen herkenbaar Discord Fix-overzicht terug.");
    }
    renderItems(data.items);
    renderSources(data.sources);
    ui["count-important"].textContent = String(Number(data.counts.important) || 0);
    ui["count-reply"].textContent = String(Number(data.counts.reply) || 0);
    ui["count-later"].textContent = String(Number(data.counts.later) || 0);
    const total = Array.isArray(data.items) ? data.items.length : 0;
    ui["result-count"].textContent = `${total} ${total === 1 ? "bericht" : "berichten"}`;
    const generated = formatDate(data.generated_at);
    setStatus(generated ? `Bijgewerkt ${generated}` : "Overzicht bijgewerkt.");
  } catch (error) {
    const message = error.name === "TimeoutError"
      ? "De lokale Discord Fix-server reageert niet op tijd."
      : error.name === "TypeError"
        ? "Geen verbinding. Controleer of Discord Fix openstaat en de lokale koppeling klopt."
        : error.message || "Het overzicht kon niet worden geladen.";
    setStatus(message, "error");
  } finally {
    state.loading = false;
    ui.refresh.disabled = false;
    if (state.refreshPending) {
      state.refreshPending = false;
      loadDashboard();
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
  state.preferences = { ...DEFAULT_PREFERENCES, ...(stored.preferences || {}) };
  state.view = VIEW_TITLES[stored.view] ? stored.view : "Overview";
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
      setStatus("Lokale toegang is ingetrokken. Verbind opnieuw om toestemming te geven.");
      ui.status.dataset.state = "error";
    } catch {
      await chrome.storage.local.remove("dashboardUrl");
    }
  }
  ui.connection.hidden = false;
  ui.dashboard.hidden = true;
  ui["settings-toggle"].hidden = true;
  ui.refresh.hidden = true;
  if (!ui.status.textContent) setStatus("Nog niet verbonden met Discord Fix.");
}

ui["connection-form"].addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = ui["dashboard-url"].value;
  try {
    const baseUrl = normalizeDashboardUrl(input);
    const granted = await chrome.permissions.request({ origins: [API_ORIGIN_PERMISSION] });
    if (!granted) throw new Error("Toegang tot de lokale Discord Fix-server is niet verleend.");
    await chrome.storage.local.set({ dashboardUrl: baseUrl });
    state.baseUrl = baseUrl;
    showConnected();
  } catch (error) {
    ui.connection.classList.add("connection-error");
    const paragraph = ui.connection.querySelector(".connection-help");
    paragraph.textContent = error.message || "De URL kon niet worden gevalideerd.";
    paragraph.classList.add("connection-error");
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
    await chrome.storage.local.set({ view: state.view });
    updateViewControls();
    loadDashboard();
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
  await chrome.storage.local.set({ preferences: state.preferences });
  applyPreferences();
  if (state.preferences.showSources && state.baseUrl) loadDashboard();
}

[ui.theme, ui.density, ui["show-counts"], ui["show-sources"]].forEach((control) => {
  control.addEventListener("change", savePreferences);
});

ui.disconnect.addEventListener("click", async () => {
  state.baseUrl = "";
  await chrome.storage.local.remove("dashboardUrl");
  await chrome.permissions.remove({ origins: [API_ORIGIN_PERMISSION] });
  ui.preferences.hidden = true;
  ui["settings-toggle"].setAttribute("aria-expanded", "false");
  ui["settings-toggle"].hidden = true;
  ui.refresh.hidden = true;
  ui.connection.classList.remove("connection-error");
  ui.connection.querySelector(".connection-help").textContent =
    "De extensie vraagt pas bij verbinden toegang tot de lokale Discord Fix-server. Hij leest geen Discord-tabbladen.";
  ui.connection.querySelector(".connection-help").classList.remove("connection-error");
  ui.connection.hidden = false;
  ui.dashboard.hidden = true;
  ui["settings-toggle"].hidden = true;
  ui.refresh.hidden = true;
  ui["dashboard-url"].value = "";
  setStatus("Verbinding gewist.");
});

matchMedia("(prefers-color-scheme: light)").addEventListener("change", () => {
  if (state.preferences.theme === "system") applyPreferences();
});

initialize().catch(() => {
  ui.connection.hidden = false;
  ui.dashboard.hidden = true;
  setStatus("De browserinstellingen konden niet worden gelezen.", "error");
});
