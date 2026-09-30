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
    this.style = { setProperty() {} };
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

async function fixture({ stored = {}, granted = true, fetch, storageError = false, html = page, js = script } = {}) {
  const elements = Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map((match) => [match[1], new Element()]));
  const views = [...html.matchAll(/data-view="([^"]+)"/g)].map((match) => {
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
      addEventListener() {},
    },
    matchMedia: () => ({ matches: false, addEventListener() {} }),
    window: { location: { pathname: "/test_dashboard_token_123456789/" }, setTimeout: () => ++timeoutId, clearTimeout() {}, setInterval() {} },
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
  vm.runInContext(js, context);
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

function snapshotResponse(overrides = {}) {
  return { ok: true, json: async () => ({
    items: [{ id: "101", content: "Preview text", state: "open", channel_name: "Test channel" }],
    sources: [], counts: { important: 1, reply: 2, later: 0, total: 145, other: 142 },
    generated_at: "2026-09-30T12:00:00Z", groups: [],
    pagination: { offset: 0, limit: 60, total: 145, anchor: 145, has_more: true },
    workflow: { enabled: true, nonce: "session_nonce" }, ...overrides,
  }) };
}

test("pagination preserves the boundary and shows the full matching count", async () => {
  const f = await fixture({ stored: { dashboardUrl: url }, fetch: async (address) => snapshotResponse({ pagination: { offset: Number(new URL(address).searchParams.get("offset")), limit: 60, total: 145, anchor: 145, has_more: true } }) });
  assert.equal(f.elements["result-count"].textContent, "145 messages");
  assert.equal(f.elements["page-label"].textContent, "Page 1 of 3");
  f.elements["next-page"].listeners.click(); await tick();
  const next = new URL(f.calls[1].address);
  assert.equal(next.searchParams.get("offset"), "60");
  assert.equal(next.searchParams.get("anchor"), "145");
  assert.equal(f.elements["page-label"].textContent, "Page 2 of 3");
});

test("details show full content, English reasons and scoped saved summaries", async () => {
  const f = await fixture({ stored: { dashboardUrl: url }, fetch: async (address) => address.includes("api/message") ? { ok: true, json: async () => ({ id: "101", channel: "123", guild: "456", conversation: "123", channel_name: "Planning", content: "Full context " + "x".repeat(1000), reasons: [{text:"You marked this as important."}], source: {name:"Test export",status:"imported",coverage:"Own sent messages only."}, state:"open", revision:"rev" }) } : snapshotResponse() });
  await f.run('loadDetail("101")');
  assert.equal(f.elements.detail.hidden, false);
  assert.match(f.elements["detail-content"].textContent, /Full context.*You marked this as important/);
  assert.match(f.elements["detail-content"].textContent, /Imported.*Own sent messages/);
  assert.match(f.elements["detail-content"].textContent, /Read saved server summary/);
  assert.match(f.elements["detail-content"].textContent, /They do not send or change Discord messages/);
});

test("explicit local actions use the session nonce and provide Undo", async () => {
  const f = await fixture({ stored: { dashboardUrl: url }, fetch: async (_address, options) => options.method === "POST" ? { ok: true, json: async () => ({id:"101", revision:"new_rev", undo:"undo_ticket"}) } : snapshotResponse() });
  await f.run('sendAction({id:"101",revision:"rev"}, "complete")');
  const post = f.calls.find((call) => call.options.method === "POST");
  assert.equal(post.options.headers["X-Discord-Fix-Nonce"], "session_nonce");
  assert.equal(JSON.parse(post.options.body).action, "complete");
  assert.equal(f.elements["undo-action"].hidden, false);
  assert.match(f.elements["action-status"].textContent, /Local follow-up saved/);
});

test("an old action cannot restore state after reconnecting to the same URL", async () => {
  const pending = deferred();
  const f = await fixture({ stored: { dashboardUrl: url }, fetch: async (_address, options) => options.method === "POST" ? pending.promise : snapshotResponse() });
  const action = f.run('sendAction({id:"101",revision:"rev"}, "complete")');
  await f.run("disconnect()");
  f.run(`state.baseUrl = ${JSON.stringify(url)}; ++state.connectionEpoch`);
  pending.resolve({ok:true,json:async()=>({id:"101",revision:"new_rev",undo:"private_old_ticket"})});
  await action;
  assert.equal(f.run("state.undo"), null);
  assert.equal(f.elements["undo-action"].hidden, true);
});

test("presets and saved filters persist without altering source text", async () => {
  const stored = {};
  const f = await fixture({stored});
  f.elements.preset.value = "focus"; f.elements.preset.listeners.change(); await tick();
  assert.equal(stored.preferences.textSize, 18);
  assert.equal(stored.preferences.showMetadata, false);
  f.elements["saved-name"].value = "Planning";
  f.elements.search.value = "decision";
  await f.elements["save-view"].listeners.click();
  assert.equal(stored.savedViews[0].q, "decision");
  assert.equal(stored.savedViews[0].name, "Planning");
});

test("since-visit rejects invalid dates and sends an existing valid visit", async () => {
  const invalid = await fixture({stored: {lastVisit:"2026-09-30"}});
  assert.equal(invalid.elements["since-visit"].disabled, true);
  const f = await fixture({stored: {dashboardUrl:url,lastVisit:"2026-09-29T12:00:00Z"},fetch:async()=>snapshotResponse()});
  f.elements["since-visit"].checked = true;
  f.elements["since-visit"].listeners.change(); await tick();
  assert.equal(new URL(f.calls[1].address).searchParams.get("since"), "2026-09-29T12:00:00Z");
});

test("standalone dashboard accepts the latest view after a delayed request", async () => {
  const html = readFileSync(join(directory, "..", "discord_fix", "dashboard.html"), "utf8");
  const js = html.match(/<script>([\s\S]*?)<\/script>/)[1];
  const requests = [deferred(), deferred()]; let index = 0;
  const f = await fixture({html,js,fetch:()=>requests[index++].promise});
  f.elements.navigation.listeners.click({target:{closest:()=>({dataset:{view:"Needs Reply"}})}});
  requests[1].resolve(snapshotResponse({items:[{content:"Latest result",state:"open"}]})); await tick();
  requests[0].resolve(snapshotResponse({items:[{content:"Obsolete result",state:"open"}]})); await tick();
  assert.match(f.elements["message-rows"].textContent, /Latest result/);
  assert.doesNotMatch(f.elements["message-rows"].textContent, /Obsolete result/);
  assert.equal(f.calls[0].options.signal.aborted, true);
});
