# Development state — 26 September 2026

The original README remains the product specification. Version 0.4 implements the local Phase 1 application paths, including adjustable display controls and a loopback-only, read-only browser dashboard; public/production acceptance is not claimed. Any client-level Discord integration remains contingent on explicit official authorization.

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
- `web_dashboard.py`, `dashboard.html`: token-gated localhost dashboard backed by fresh SQLite read-only connections, a restricted GET-only API, no cross-origin access, and automatic browser refresh. Synthetic preview rows have no Discord links.
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
