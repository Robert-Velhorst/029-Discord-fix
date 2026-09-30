// Dependency-free tests of the packaged script; browser layout is checked separately.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const vm = require("node:vm");

const directory = join(__dirname, "..", "browser-extension");
const page = readFileSync(join(directory, "sidepanel.html"), "utf8");
const script = readFileSync(join(directory, "sidepanel.js"), "utf8");
const url = "http://127.0.0.1:4567/test_dashboard_token_123456789/";
const tick = () => new Promise((resolve) => setImmediate(resolve));
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};

class Element {
  constructor() {
    this.dataset = {};
    this.attributes = {};
    this.children = [];
    this.listeners = {};
    this.hidden = false;
    this.value = "";
    this.checked = false;
    this.disabled = false;
    this.text = "";
  }
  get childElementCount() { return this.children.length; }
  get textContent() { return this.text + this.children.map((child) => child.textContent).join(""); }
  set textContent(value) { this.text = String(value); this.children = []; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.text = ""; this.children = children; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  removeAttribute(name) { delete this.attributes[name]; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  focus() { this.focused = true; }
}

async function fixture({ stored = {}, granted = true, fetch, storageError = false } = {}) {
  const elements = Object.fromEntries([...page.matchAll(/id="([^"]+)"/g)].map((match) => [match[1], new Element()]));
  const views = [...page.matchAll(/data-view="([^"]+)"/g)].map((match) => {
    const button = new Element();
    button.dataset.view = match[1];
    return button;
  });
  const calls = [];
  let timeoutId = 0;
  const context = vm.createContext({
    URL, URLSearchParams, AbortController, Intl, Date, console,
    document: {
      documentElement: new Element(),
      getElementById: (id) => elements[id],
      querySelectorAll: () => views,
      createElement: () => new Element(),
    },
    matchMedia: () => ({ matches: false, addEventListener() {} }),
    window: { setTimeout: () => ++timeoutId, clearTimeout() {}, setInterval() {} },
    chrome: {
      storage: { local: {
        get: async () => stored,
        set: async (value) => { if (storageError) throw Error("localized browser error"); Object.assign(stored, value); },
        remove: async () => { if (storageError) throw Error("localized browser error"); delete stored.dashboardUrl; },
      } },
      permissions: { contains: async () => granted, request: async () => granted, remove: async () => true },
    },
    fetch: (address, options) => {
      calls.push({ address, options });
      return fetch ? fetch(address, options) : Promise.resolve(response("example"));
    },
  });
  vm.runInContext(script, context);
  await tick();
  return { elements, views, calls, context, run: (expression) => vm.runInContext(expression, context) };
}

function response(content) {
  return { ok: true, json: async () => ({
    items: [{ content, state: "open", channel_name: "Test channel" }],
    sources: [], counts: { important: 1, reply: 2, later: 0 }, generated_at: "2026-09-30T12:00:00Z",
  }) };
}

test("fresh panel shows an English connection status", async () => {
  const f = await fixture();
  assert.equal(f.elements.status.textContent, "Not connected to Discord Fix.");
  assert.equal(f.elements.connect.disabled, false);
  assert.equal(f.elements.dashboard.hidden, true);
  assert.equal(f.calls.length, 0);
});

test("invalid stored preferences and inherited view keys fall back safely", async () => {
  const f = await fixture({ stored: { preferences: { theme: "invalid", density: 123, showCounts: "false", showSources: null }, view: "constructor" } });
  assert.equal(f.elements.theme.value, "system");
  assert.equal(f.elements.density.value, "comfortable");
  assert.equal(f.elements["show-counts"].checked, true);
  assert.equal(f.run("state.view"), "Overview");
});

test("revoked host permission stops background fetches and explains recovery", async () => {
  const f = await fixture({ stored: { dashboardUrl: url }, granted: false });
  await f.run("loadDashboard()");
  assert.equal(f.calls.length, 0);
  assert.equal(f.elements.connection.hidden, false);
  assert.equal(f.elements["dashboard-url"].value, url);
  assert.match(f.elements.status.textContent, /revoked.*Connect again/);
});

test("invalid input gets an English alert and focused, marked input", async () => {
  const f = await fixture();
  f.elements["dashboard-url"].value = "https://example.org/";
  await f.elements["connection-form"].listeners.submit({ preventDefault() {} });
  assert.equal(f.elements["connection-error"].hidden, false);
  assert.match(f.elements["connection-error"].textContent, /Paste the full Discord Fix link/);
  assert.equal(f.elements["dashboard-url"].getAttribute("aria-invalid"), "true");
  assert.equal(f.elements["dashboard-url"].focused, true);
});

test("the latest view wins even if an aborted fetch completes late", async () => {
  const requests = [deferred(), deferred()];
  let index = 0;
  const f = await fixture({ stored: { dashboardUrl: url }, fetch: () => requests[index++].promise });
  const latest = f.run('state.view = "Needs Reply"; updateViewControls(); loadDashboard()');
  assert.equal(f.calls[0].options.signal.aborted, true);
  requests[1].resolve(response("Latest result"));
  await latest;
  requests[0].resolve(response("Old result"));
  await tick();
  assert.match(f.elements.items.textContent, /Latest result/);
  assert.doesNotMatch(f.elements.items.textContent, /Old result/);
  assert.equal(f.elements["view-title"].textContent, "Needs reply");
  assert.equal(f.elements.refresh.disabled, false);
});

test("typing invalidates results before the debounce starts a new request", async () => {
  const pending = deferred();
  const f = await fixture({ stored: { dashboardUrl: url }, fetch: () => pending.promise });
  f.elements.search.value = "new query";
  pending.resolve(response("Wrong search result"));
  await tick();
  assert.equal(f.elements.items.childElementCount, 0);
});

test("disconnect clears message data and rejects late responses", async () => {
  const pending = deferred();
  const f = await fixture({ stored: { dashboardUrl: url }, fetch: () => pending.promise });
  f.run('renderItems([{content:"Private old row"}])');
  await f.run("disconnect()");
  pending.resolve(response("Private late row"));
  await tick();
  assert.equal(f.elements.items.childElementCount, 0);
  assert.equal(f.elements.dashboard.hidden, true);
  assert.equal(f.elements["count-important"].textContent, "0");
  assert.match(f.elements.status.textContent, /Connection cleared/);
});

test("storage failure does not prevent clearing displayed data", async () => {
  const f = await fixture({ stored: { dashboardUrl: url }, storageError: true });
  assert.match(f.elements.items.textContent, /example/);
  await f.run("disconnect()");
  assert.equal(f.elements.items.childElementCount, 0);
  assert.equal(f.elements.connection.hidden, false);
  assert.match(f.elements.status.textContent, /Disconnected for this session/);
  assert.equal(f.elements.connect.disabled, false);
});

test("failed preference persistence still applies the chosen theme", async () => {
  const f = await fixture({ storageError: true });
  f.elements.theme.value = "light";
  f.elements.density.value = "compact";
  await f.run("savePreferences()");
  assert.equal(f.run("document.documentElement.dataset.theme"), "light");
  assert.match(f.elements.status.textContent, /could not be saved/);
  assert.doesNotMatch(f.elements.status.textContent, /localized browser error/);
});

test("workflow and deletion labels do not falsely request attention", async () => {
  const f = await fixture();
  f.run('renderItems([{state:"complete",important:true,reply:true,content:"Done"},{deleted:true,content:"Removed text",important:true}])');
  assert.match(f.elements.items.textContent, /Completed/);
  assert.match(f.elements.items.textContent, /Deleted at the source/);
  assert.doesNotMatch(f.elements.items.textContent, /Needs reply|Important|Removed text/);
  assert.equal(f.run('safeDiscordUrl("https://discord.com/channels/1/2/3")'), "https://discord.com/channels/1/2/3");
  assert.equal(f.run('safeDiscordUrl("https://user:secret@discord.com/channels/1/2/3")'), "");
});

test("expired dashboard leaves a visible recovery message and no stale rows", async () => {
  const f = await fixture({ stored: { dashboardUrl: url }, fetch: async () => ({ ok: false, status: 404 }) });
  assert.match(f.elements.status.textContent, /expired/);
  assert.equal(f.elements.status.dataset.state, "error");
  assert.equal(f.elements.items.childElementCount, 0);
  assert.equal(f.elements["count-important"].textContent, "—");
  assert.equal(f.elements.refresh.disabled, false);
});
