# Development state — 30 September 2026

The specification is `PRODUCT-SPECIFICATION.md`; setup is in `README.md`. Desktop 0.4 and extension 0.2.0 implement local companion paths and a loopback dashboard with explicit local follow-up actions. Public/production acceptance is not claimed. Historical notes below describe earlier builds; the latest scope is recorded at the end.

## Run and verify

- Source run: `python -m discord_fix` (Python 3.11+, Tcl/Tk, SQLite FTS5).
- Windows package: `DiscordFix.exe`, Python bundled by PyInstaller.
- Browser companion: unpacked Manifest V3 extension in `browser-extension/`; local development package can be created with `Package-Browser-Extension.ps1`.
- Tests: `python -W error::ResourceWarning -m unittest discover -s tests -v`.
- Lint/format: `ruff check .` and `ruff format --check .` (ruff 0.16.7).
- Packaged diagnostic: `DiscordFix.exe --self-test <absolute-report.json>`.
- Rebuild: `Build-Windows.ps1` with PyInstaller 6.22.0 installed.
- GitHub Actions checks are defined in `.github/workflows/test.yml`; local verification does not imply a passing remote CI run. No deployment has occurred.

## Implemented modules

- `store.py`: additive migration from the original SQLite schema, transactional import/sync, workflow overrides, FTS5 maintenance, source/freshness records, exclusions, deadline/snooze maintenance, notifications, audit metadata, export, retention and consistent backups.
- `importer.py`: bounded ZIP reader for JSON/legacy CSV channel message exports; no extraction, account credentials or attachment fetching; partial-record errors and duplicate archive-name rejection.
- `connector.py`: official bot-only read adapter, explicit channel/thread allowlist, permission overwrite calculation, paginated recent history, rate-limit cooldowns, revoked/offline state and bounded deletion reconciliation. No message send route.
- `priority.py`: deterministic reasons using mentions/replies, configured people/servers/channels/topics and confirmed deadlines; manual overrides win.
- `summaries.py`: extractive and actual HTTP model adapters, per-claim citation validation, per-conversation incremental updates, daily/full reconciliation, four-level hierarchy, private corrections and optimistic snapshot validation.
- `network.py`: bounded JSON requests, timeouts and no redirects/proxies forwarding private data.
- `vault.py`: Windows user-scoped DPAPI, no plaintext fallback, external AI keys isolated by exact endpoint.
- `instance.py`: per-database OS lock.
- `__main__.py`, `panels.py`, `widgets.py`, `appearance.py`: native dashboard/dialogs, adjustable light/Ash/dark/Onyx themes, high contrast, separate control/message text sizes, three row densities, persistent per-column widths, keyboard shortcuts, source management, privacy/settings, context/evidence navigation, background work, opt-in scheduler, scrollable controls and in-app notifications.
- `web_dashboard.py`, `web_data.py`, `web_workflow.py`, `dashboard.html`: loopback snapshots, pagination, details and saved-summary reading; nonce/revision/origin-checked local follow-ups with Undo; no CORS for ordinary pages or Discord write route. Demo mode removes links and disables writes.
- `diagnostics.py`: opt-in packaged smoke test using only a temporary synthetic database, including the browser dashboard.

## Verification scope

The suite covers original data migration, partial invalid imports, persistence/reimport, manual priority dominance, snooze expiry, all exclusion scopes, parent-thread exclusions, citation integrity, privacy races, cached/incremental/full summaries, previous-context model update contracts, provider failure preservation, read permission overrides, source revocation, bounded tombstones, atomic sync rollback, endpoint consent/key isolation, HTTP redirect refusal, index edits/deletions, backup handles, retention, DPAPI, single-instance locking, native dialogs and display preference persistence/readability.

A visual pass on Windows found clipped actions under display scaling. The dashboard was compacted and all main/dialog content made scrollable. Screen-reader behavior has not been accepted with a real assistive-technology user.

## Deliberate coverage limits

- Bot sync polls up to five 100-message pages per selected channel. Missing older history is labelled, not synthesized. Unselected threads are never crawled. This is not a Gateway event mirror or universal personal inbox.
- An official personal data export contains the exporting account's own sent messages. No received messages or incoming obligations are invented.
- Bot content may be empty when Discord does not grant Message Content access. The source detail explicitly states this; empty content is not proof of an empty discussion.
- Generative providers require a real locally installed model or an explicitly opted-in external endpoint. No model or paid capacity is provisioned. Provider contract tests do not establish semantic quality or real service acceptance.
- Summaries fail visibly if a message/model context exceeds the bounded processing budget. Higher levels are faithful aggregations, not additional uncited model claims. Historical summaries invalidated by privacy changes are removed along with manual correction history.
- Only current local app data is affected by retention/deletion. User-created backups/exports remain outside that scope.
- Database encryption beyond OS account controls, a signed installer, app auto-updates, mobile, voice/video and broad alternative-client access are not delivered by this release.

## Official references checked

- Discord data packages: https://support.discord.com/hc/en-us/articles/360004957991-Your-Discord-Data-Package
- Message endpoints and history/content restrictions: https://docs.discord.com/developers/resources/message
- Permission precedence: https://docs.discord.com/developers/topics/permissions
- Rate limits: https://docs.discord.com/developers/topics/rate-limits
- Ollama chat contract: https://docs.ollama.com/api/chat

## Remaining acceptance work

Use a user-authorized real export, installed server bot and chosen AI provider to validate formats, permissions, freshness and summary quality in the actual environment. Review accessibility with screen-reader use, obtain a signing identity for public Windows distribution, and assess provider-specific privacy terms before external/shared use. Those steps require access or decisions that this session does not have. No credentials have been requested in chat or invented.

## Release verification — 13 September 2026

- 31 automated tests passed on Windows/Python 3.14, with ResourceWarning enabled as an error.
- Ruff lint and format checks passed.
- The packaged executable passed its native UI/workflow, four-level summary, dialog and privacy smoke test.
- The installer was executed in isolated workspace directories; executable copy, shortcut target and installed executable smoke test passed. The actual user Start menu was not changed.
- Executable Authenticode status: NotSigned.
- No real Discord account, real private export, external AI subscription or remote CI was used.

## Interface update — 23 September 2026

- Added four color themes, high contrast, separate control and message text sizes, compact/standard/spacious rows, individually resizable persistent table columns, and keyboard shortcuts for the five views, text sizing and focus movement.
- All 35 unit and native Tk tests passed on Windows 11 / Python 3.14 with `ResourceWarning` treated as an error. Ruff 0.16.7 lint and format checks passed.
- PyInstaller 6.22.0 built `dist/DiscordFix.exe`; the packaged self-test exited 0 and passed native selection/workflow, four summary levels, all desktop dialogs and privacy exclusion using synthetic data.
- Executable SHA-256: `17AAC6337964C9AD7BF1589DD96541735993BC90DBCB0D4C8E9301EA3A07167F`. Authenticode: `NotSigned`.
- This release changes Discord Fix's own companion UI. It does not alter Discord's official client, mobile You Bar, or game overlay. Real Discord access, screen-reader acceptance and a manual accessibility-user review remain untested.

## Browser dashboard update — 26 September 2026

- Version 0.4 adds the responsive local browser dashboard. The desktop app starts a token-gated server on `127.0.0.1`, exposes only read-only GET routes, and stops the server when the app closes. The browser refreshes about every 15 seconds. Preview mode uses synthetic content and removes Discord deep links.
- The dashboard reads each snapshot through a new SQLite read-only connection. The local implementation does not add CORS access, a remote bind address, a write route, or outbound service calls.
- All 37 unit tests passed on Windows/Python 3.14 with `ResourceWarning` treated as an error. Ruff 0.16.7 lint and formatting checks passed.
- PyInstaller 6.22.0 built `dist/DiscordFix.exe`; the packaged self-test passed the native workflow, four summary levels, dashboard, desktop dialogs and privacy exclusion checks using a temporary synthetic database.
- Executable SHA-256: `829B18221C848B4E09270A02CE5E3E61D8865FE910656182D4AEEA4F48729BB6`. Authenticode: `NotSigned`.
- The ChatGPT browser was not available for this task, and its separate browser environment could not reach the loopback preview. No tunnel or public hosting was created. The app's local browser button and packaged web asset were verified through the packaged smoke test; remote rendering and screen-reader acceptance remain unverified. No WCAG conformance claim is made.

## English browser side panel — 26 September 2026

- Extension version 0.1.1 presents its interface, controls, status messages, source-status labels, and dates in English. User-provided Discord message text, channel names, and author names remain unchanged.
- The English setup guide is `BROWSER-EXTENSION.md`; the desktop app interface remains Dutch.
- All 40 automated tests passed with `ResourceWarning` treated as an error. Ruff lint/format, JavaScript syntax, manifest JSON, and the packaged five-file extension archive were verified.
- Browser-rendered visual acceptance remains unverified. The extension has not been loaded into the user's browser or published to an extension store.

## Browser side panel update — 26 September 2026

- Added an unpacked Chrome/Edge Manifest V3 side panel that presents the local read-only dashboard alongside the current tab. It has no Discord host access, content script, tab-reading permission, Discord credential, or write route.
- The extension asks for optional access to `http://127.0.0.1` only when the user connects a pasted local dashboard URL. It validates the loopback address and token path, sends GET requests without credentials or redirects, and can revoke its host permission when the user disconnects.
- The panel supports the five existing views, search, refresh, theme, row density, priority counters and source-status preferences. Preferences remain in extension-local storage.
- All 39 automated tests passed with `ResourceWarning` treated as an error. Ruff 0.16.7 lint/format, manifest JSON, JavaScript syntax and archive-content checks passed. `dist/Discord-Fix-Browser-Extension-0.1.0.zip` contains only the five extension files.
- Browser-rendered integration and visual QA remain unverified. The attempt to start an isolated Chrome test process was rejected by the execution environment's policy (`blocked by policy`); the extension was not loaded into the user's browser or published to a store.

## English side panel usability review — 30 September 2026

- Extension 0.1.2 adds visible English connection/status alerts and a direct **Change connection** action. Invalid input is marked and focused; successful connection focuses search. Browser storage failures use English recovery messages and do not prevent session-level settings or privacy clearing.
- Requests are cancelled and checked against their connection, view, and query before rendering. Disconnect immediately removes displayed message/source data and invalidates pending responses. Completed, dismissed, deferred, deleted, and deadline states now have English labels; source statuses use a fixed English mapping.
- Package naming now follows the manifest version and includes only the five expected extension files. The setup guide states the 60-message snapshot and 420-character preview limits.
- All 40 Python tests and 11 new dependency-free JavaScript runtime tests passed. Ruff 0.16.7 lint/format, JavaScript syntax, manifest JSON, and archive checks passed. Run the runtime suite with `node --test tests/browser_extension_runtime.test.cjs`; it is also part of GitHub Actions.
- Rendered QA used isolated, headless Chrome 154.0.8037.58 through the existing bundled Playwright runtime, a temporary synthetic SQLite database, and the real read-only dashboard HTTP server. Extension storage and permission APIs were simulated; the test harness supplied cross-origin access normally granted by extension host permissions. No backend CORS setting was changed. The Browser plugin's `browser` skill was unavailable, so regular Playwright was used.
- Verified initial/invalid connection states, all six navigation controls, search/clear, theme and density, English source status, priority-count visibility, disconnect clearing, and keyboard focus recovery. Screenshots at 280, 375, and 768 pixels showed no page-level horizontal overflow. There were no page or console errors in the successful run. Screenshots and temporary QA scripts are outside the repository.
- The Chrome API reference was checked for the toolbar/side-panel behavior: https://developer.chrome.com/docs/extensions/reference/api/sidePanel. Actual extension installation, side-panel activation, permission prompts, Edge rendering, screen-reader acceptance, and real Discord/provider access remain unverified. There is no visual regression baseline or WCAG conformance claim; no user browser profile or extension store was changed.

## English context and workflow release — 30 September 2026

- Extension 0.2.0 adds full local context, exact totals/pagination, English rule codes/reasons, known thread/reply grouping with a labelled channel fallback, and coverage/freshness. Saved-summary reading covers personal/conversation/channel/server levels, paginated entries, citations, and corrections. It does not generate summaries or contact a provider.
- Explicit local Complete/Dismiss/Reopen/Snooze/priority/reply actions require a session nonce, expected revision, valid host, and allowed supplied origin. Transactions guard concurrent changes. Monotonic per-item revisions prevent Undo after an intervening change, including a change back to the previous value. Tickets are session-only and bounded to 500. Ambiguous failed saves are not retried automatically.
- An additive sequence table keeps page insertion boundaries after deletion of the highest message row. Deleted IDs leave that table. Edits, removals, expiry, and follow-up changes remain live. App restart does not invent new messages.
- Saved summary evidence is rechecked against all saved source hashes, exclusions, deleted rows, bot availability, and citation quotes. Changed or excluded evidence hides the whole summary, including uncited source text that may have influenced it. This is not a semantic truth validator.
- Added local pins, 20 named view/search combinations, previous-visit filtering, Focus/Compact/Context presets, text sizes, and metadata visibility. The desktop browser action opens an English manual pairing window with an explicit copy button. No native host, signing, publication, or automatic installation was added.
- The standalone Dutch dashboard now cancels/identifies requests, times out, clears obsolete results, pages all matches, reads full context, and distinguishes groups. Its interface offers reading; panel workflow uses the restricted action endpoint.
- Verification: 55 Python tests, 18 JavaScript runtime tests, Ruff lint/format, JavaScript syntax, archive contents, and rebuilt Windows executable/self-test. The executable is unsigned. The archive contains exactly five extension resources. Native tests instantiate/reopen the English pairing window with browser launch mocked. The own-export author placeholder is English while the stored source record is preserved.
- Chrome UI checks used CUA, 145 synthetic records, and real local HTTP snapshots/details/summary/action routes. Storage/permission APIs were simulated in a labelled preview outside the repository. Observed full context/English reasons, Complete/Undo, coverage, grouped/pinned results, summary citations, pagination, and Focus text size/count visibility. No warning/error console entries were captured there.
- Screenshot capture timed out; viewport overrides did not produce the requested 320 CSS-pixel width. This pass does not establish screenshot or 320-pixel reflow acceptance. Earlier screenshots are not proof for this build. Real installation/activation, permission prompts, restart/revocation recovery, Edge, screen readers, and real sources remain gaps. Installation awaits the user's response to the browser confirmation.
- Discord navigation/Appearance/Accessibility were inspected in an existing login without creating an account, changing settings, or reading private chat contents. See `DISCORD-UI-RESEARCH.md`. This provides no general ingestion access and does not implement the overlay.

## Optional Windows pairing — extension 0.3.0 — 30 September 2026

- Added an English **Connect with desktop app** path through optional native messaging. The extension requests native/local-site access only on an explicit click. Manual pairing and pre-connection access clearing remain available. Clear waits for an outstanding permission prompt before revoking access, serializes URL removal after a pending save, and rejects late host replies. Local-site revocation and saved-URL changes clear obsolete displayed data.
- The separate Windows host permits only explicitly listed extension origins, accepts one bounded framed pairing command, reads the configured app's DPAPI-encrypted session record, and checks a matching live loopback handshake. It returns the session URL without messages, provider credentials, or arbitrary RPC. The build does not register it. Preparation writes only helper files/configuration; registration and unregistration require explicit script switches. Existing files are backed up, and conflicting registrations are preserved.
- Verification: the original 55 Python checks and 11 new native-pairing/installer checks passed on Windows/Python 3.14, with ResourceWarning treated as an error. All 26 dependency-free JavaScript runtime tests passed, including denied access, missing/malicious helpers, pending permission grants and URL saves, late responses, and immediate private-data clearing. Ruff lint/format and JavaScript syntax checks passed.
- Rebuilt unsigned `DiscordFix.exe` and `DiscordFixPairing.exe`. The desktop self-test passed its five existing native workflow/summary/dashboard/dialog/privacy checks. A copied helper executable in a temporary directory passed real binary framed IPC, DPAPI/HTTP handshake, unknown-origin rejection, and stopped-session rejection. Preparation/backup/WhatIf/invalid-ID checks preserved browser registry entries. No actual native-host registration or browser extension installation was performed.
- Chrome CUA interactions checked the English connection page, simulated native pairing, 145 real synthetic HTTP results, and connection clearing. Extension storage, native messaging, and permission APIs were explicitly simulated in a labelled preview outside the repository. A screenshot of the connection page was captured at the browser's existing viewport; it does not prove 320-pixel reflow or installed side-panel sizing.
- Real Chrome/Edge host registration/launch, extension installation/activation, permission prompts, restart/revocation behavior, assistive technology, and authorized real-source/provider acceptance remain unverified. This release remains a companion and does not deliver the requested Discord overlay. Installation confirmation is pending; signing/store publication has not been requested.

## Narrow-panel usability — extension 0.3.1 — 1 October 2026

- At 320 CSS pixels, the 0.3.0 view-navigation region measured 292 pixels wide with 481 pixels of horizontal content. Several views were outside the visible region. In 0.3.1 the buttons wrap into two rows; both widths measure 292 pixels. All six view buttons fit inside the page. Text buttons now have a minimum height of 28 CSS pixels, including connection and return controls.
- Chrome CUA device emulation established actual CSS viewport widths of 320, 375, 768, and 1440 pixels. At each measured width the updated message-list page's scroll width equalled its viewport width. At 320 pixels, open settings, light theme, 22-pixel message text, and full message context also had no page-level horizontal overflow. The normal viewport override initially stopped at 427 pixels; it was reset before device emulation, and all temporary emulation was cleared afterward.
- Keyboard observation in the 0.3.0 preview covered Tab from search to context summary, Enter to open it, Shift+Tab to the return control, and Enter back to search. The same return sequence was observed in 0.3.1 message context. This is a bounded keyboard check, not a complete accessibility audit. No JavaScript behavior changed in this patch.
- Used 145 synthetic records and real local HTTP routes. Browser storage, native messaging, and permission APIs remained simulated. Saved before/after screenshots outside the repository show the navigation change at 320 pixels. No committed visual-regression baseline exists; visual regression is inconclusive. No warning/error entries were captured in the updated preview. Core Web Vitals, axe, screen-reader behavior, and a full WCAG assessment were not measured.
- Three focused Python extension checks and all 26 JavaScript runtime checks passed. The 0.3.1 archive contains the five extension resources. Actual installation, native-host/browser permission behavior, Edge, real sources, and the original overlay remain open; this preview does not establish those outcomes.
