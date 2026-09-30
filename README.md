# Discord Fix

Discord Fix is a Windows-first companion that helps people make sense of Discord information they are authorized to access. It brings available messages, follow-ups, and context into a calmer dashboard with clear source links.

> **Current release: desktop 0.4 development build / extension 0.3.0.** This is a local development release, not a published or signed product. It includes a Windows desktop app, a local browser dashboard, and an optional Chrome/Edge side panel. The desktop app and standalone dashboard are currently in Dutch; the extension controls, explanations, dates, and recovery messages are in English. Source messages and names retain their original language.

## What Discord Fix does

- Organizes available information into **Important Now**, **Needs Reply**, **Conversations**, **Later**, and **Everything**.
- Imports a user-provided Discord data package and can read selected channels through an official, read-only Discord bot connection.
- Provides search, source details, follow-up states, manual priority controls, reminders, and source-linked context summaries.
- Offers adjustable themes, high contrast, text sizes, row density, resizable columns, keyboard navigation, and focus mode.
- Keeps its working database on the computer. Optional AI processing is off until configured by the user.
- Can show the same local dashboard in a Chrome or Edge side panel next to Discord.

Discord Fix is a companion, **not a replacement Discord client or a full-screen overlay**. The browser extension does not inject into, inspect, or change Discord pages. It reads the local dashboard and saves your personal follow-up choices to Discord Fix. Those choices never change or send Discord messages.

The originally requested customizable Discord shell remains open. The [integration assessment](OVERLAY-INTEGRATION-ASSESSMENT.md) records the official routes reviewed, their limits, and a prepared authorization inquiry that has not been sent.

## Run from source on Windows

Requirements: Python 3.11 or later and a Windows installation that includes Tcl/Tk. No third-party Python packages are needed to run the source version.

1. Install Python 3.11 or later with Tcl/Tk enabled.
2. Clone the repository and start Discord Fix:

   ```powershell
   git clone https://github.com/Robert-Velhorst/029-Discord-fix.git
   cd 029-Discord-fix
   python -m discord_fix
   ```

You can also double-click `Start-Discord-Fix.cmd`. The app creates its local data folder under `%LOCALAPPDATA%\DiscordFix`. It starts with an empty inbox: it does not connect an account, import data, or contact an AI provider on its own.

This repository does not include a ready-to-install Windows executable. To build one on Windows, install PyInstaller in your Python environment and run `Build-Windows.ps1`. The resulting executable is unsigned. `Install-Discord-Fix.ps1` installs a locally built executable for the current Windows user and creates a Start-menu shortcut.

## Use the browser side panel

The side panel is an optional, unpublished development extension. It is available in a normal Chrome or Edge browser, not in ChatGPT's built-in browser or the Discord desktop app.

1. Start Discord Fix and choose **Browserdashboard**. Keep the desktop app open.
2. Use **Copy private connection address** in the English connection window.
3. Open `chrome://extensions` or `edge://extensions`, enable **Developer mode**, and choose **Load unpacked**.
4. Select this repository's `browser-extension` folder.
5. Open the Discord Fix extension panel, paste the local dashboard address, and choose **Connect**. Allow its requested local-site permission.

For pairing without copying the address, optionally build and register the Windows pairing helper for your exact extension ID, then select **Connect with desktop app**. The [English extension guide](BROWSER-EXTENSION.md#optional-windows-pairing-helper) explains setup, permissions, and removal. Manual connection remains available; neither the app nor the build script registers browser access automatically.

The English panel includes search with exact matching totals, **Previous/Next** pages, full local message context, English priority reasons, and source/freshness details. **Conversations** groups known threads and linked replies; missing relationships have an explicitly labelled channel fallback. Complete, dismiss, reopen, snooze, or change personal priority/reply status in the detail view, then use **Undo**. These actions update the local database only.

Use **Since last visit** for newly received or edited local records. Read saved source-linked summaries; generate or update them in the desktop app. Choose Focus/Compact/Context presets, text sizes, themes, spacing, and metadata visibility. Pin conversations and save view/search combinations on this device. Pages have up to 60 previews of 420 characters; context retrieves full locally available text up to one million characters. Paging uses an insertion boundary; refresh to include newly imported messages. Existing edits, removals, and workflow changes remain live.

Keep the desktop app open. Use **Change connection** after restarting it. The local address contains a temporary access token: keep it private. Closing Discord Fix stops the dashboard session and expires its Undo tickets. Preferences, pins, saved searches, and visit time remain in extension-local storage when you clear the connection.

To create a ZIP of the extension files, run `Package-Browser-Extension.ps1`. This does not publish the extension to an extension store.

## Connect or import information

**Import your own data package.** In the desktop app, choose **Discord-datapakket importeren** and select the ZIP file. The importer supports the documented per-channel `messages.json` and legacy `messages.csv` forms. A personal Discord export primarily contains messages sent by the exporting account; it is not a complete inbox and does not provide other people's replies.

**Connect an official bot.** A server administrator must install the bot and grant it access to selected channels. In Discord Fix, add the bot and specify the channel or thread IDs you are allowed to use. The connector checks bot identity and channel permissions, reads recent history, and does not send messages. It does not provide general access to personal direct messages or crawl unselected threads. Message content may be unavailable if Discord has not granted the application the necessary access.

**Choose summary processing.** Extractive summaries work locally without a model. Optional local Ollama or an explicitly configured external compatible provider can be selected in settings. External processing sends the selected message text and associated context to that provider; review its data handling and costs before enabling it. Discord Fix does not automatically send replies or take external actions based on AI output.

See the [Windows user guide — Dutch](USER-GUIDE.nl.md) and the [browser extension guide — English](BROWSER-EXTENSION.md) for detailed setup steps. The [development and verification notes](DEVELOPMENT.md) and [product specification](PRODUCT-SPECIFICATION.md) are also in English.

## Privacy and access boundaries

- Discord Fix does not use personal Discord account tokens, self-bots, hidden page scraping, or message-sending routes.
- The browser extension has no Discord-site permission or content script. It requests optional access to `http://127.0.0.1` only when connecting to the local dashboard.
- Optional native pairing requests `nativeMessaging` only on an explicit click. The separately registered helper permits only listed extension IDs and returns a live, verified local session address. Its session record is encrypted with Windows DPAPI. **Clear connection** removes the saved browser URL and revokes both optional permissions.
- The desktop dashboard listens on this computer only. Reads use SQLite snapshots. Explicit local actions require the private URL, a separate session nonce, and a current item revision; stale writes are rejected. Actions have no Discord API write path.
- Bot tokens and configured provider keys use Windows DPAPI. The message database is a local SQLite file protected by Windows account access; it does not have separate application-level encryption.
- AI providers are not contacted until the user configures and chooses them. No model, subscription, or external service is provisioned by this repository.
- Exports and backups can contain private conversation data. Keep them in a location you trust.

## Development and checks

Run the automated suite with:

```powershell
python -W error::ResourceWarning -m unittest discover -s tests -v
```

Run lint and formatting checks with Ruff:

```powershell
ruff check .
ruff format --check .
```

The browser extension uses plain JavaScript. If Node.js is installed, its syntax can be checked with:

```powershell
node --check browser-extension/service-worker.js
node --check browser-extension/sidepanel.js
node --test tests/browser_extension_runtime.test.cjs
```

The project also contains a GitHub Actions workflow at `.github/workflows/test.yml`.

## Known limitations

- This release does not replace Discord, reskin its interface, or provide an overlay over the Discord app or website.
- Coverage depends on the data package or bot permissions provided. A data package is not a full inbox; a bot sees only authorized channels and bounded recent history.
- The browser extension has not been published to the Chrome Web Store or Microsoft Edge Add-ons. Its HTML, controls, and connection flow have been checked in isolated Chrome with synthetic local data and simulated extension APIs. Installation, side-panel activation, and permission prompts in a real extension session remain unverified.
- Discord navigation, Appearance, and Accessibility were inspected in an existing logged-in Chrome session on 30 September 2026. No account was created, private conversation content was used, or account setting was changed. Real-export, real-bot, and real-provider acceptance remain open. Automated provider-contract checks do not establish summary quality or provider acceptance.
- Screen-reader acceptance has not been completed and no WCAG conformance claim is made.
- The Windows executable is unsigned. Mobile, voice/video, general personal-DM access, and replies from Discord Fix are outside this development release.

## Project documents

- [Product specification and longer-term requirements](PRODUCT-SPECIFICATION.md)
- [Development and verification notes](DEVELOPMENT.md)
- [Windows user guide — Dutch](USER-GUIDE.nl.md)
- [Browser extension guide — English](BROWSER-EXTENSION.md)
- [Live Discord UI observations](DISCORD-UI-RESEARCH.md)
- [Improvement plan and acceptance gaps](IMPROVEMENT-ROADMAP.md)
