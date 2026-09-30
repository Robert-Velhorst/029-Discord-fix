# Discord Fix browser side panel for Chrome and Edge

Extension **0.2.0** displays local Discord Fix information in a browser side panel. Controls, explanations, dates, and recovery messages are English; source messages and names retain their original language. It does not read or modify Discord pages. It reads the local dashboard and saves your personal follow-up choices locally.

The extension does not need access to Discord. When you connect a dashboard URL, the browser asks for optional access to `http://127.0.0.1/*`. The URL contains a temporary random access token and is stored in the extension's local browser storage. Keep it private.

The browser permission covers HTTP ports on `127.0.0.1`. The extension accepts one explicit port and private token path, omits credentials, and rejects redirects. Reads use GET. Explicit local follow-up actions use POST with a separate session nonce and current item revision. The server checks the host and any supplied origin. **Clear connection** removes the saved URL and revokes local-site permission.

## Install the development extension

The extension has not been published to the Chrome Web Store or Microsoft Edge Add-ons. Load it unpacked for local testing:

1. Start Discord Fix on Windows and select **Browserdashboard** (the Dutch option for opening the browser dashboard). Keep the app open.
2. Select **Copy private connection address** in the English connection window. If necessary, copy the complete `http://127.0.0.1:...` URL from the address bar instead.
3. Open `chrome://extensions` in Chrome or `edge://extensions` in Edge and turn on **Developer mode**.
4. Select **Load unpacked** and choose this repository's `browser-extension` folder.
5. Open the Discord Fix side panel using the extension's toolbar icon. Paste the local dashboard URL, select **Connect**, and grant the requested local-site permission.

The panel refreshes the dashboard about every 30 seconds while Discord Fix is running. If you close and later restart Discord Fix, select **Browserdashboard** again. In the panel, choose **Change connection**, then paste the new URL and connect; the old URL expires when the app closes. Connection failures appear above the dashboard, with **Refresh** available to retry.

## Use the side panel

Choose among Overview, Important, Needs reply, Conversations, Later, and Everything. Search the information already available in Discord Fix. A message's **Open original in Discord** link opens that message in a new browser tab when a valid Discord link is available.

Use **Previous/Next** to reach all matching results, with exact matching totals. A page has up to 60 previews of 420 characters. **Why this appears and full context** retrieves the full locally available text, bounded at one million characters with an explicit truncation notice. It shows English priority reasons, source coverage/status, receipt time, sync time, and server/channel IDs. Priority counts describe the database snapshot, rather than the visible search results. Completed, dismissed, deferred, and deleted states have English labels.

Paging keeps an insertion boundary; choose **Refresh** to include newly imported messages. Existing edits, removals, expiry, and workflow changes remain live, so pages are not an immutable historical export.

**Conversations** separates known threads and linked replies within a source/channel. Without those relationships, it labels a channel grouping that may contain several topics. Open a group to inspect its messages. Pin groups and use **Pinned conversations** to filter them. Newly discovered reply relationships can change a group key; repin if necessary.

Use **Display settings** for Focus/Compact/Context presets, text sizes, dark/light/system themes, row spacing, author/time visibility, priority counts, and source status. Preferences are stored in extension-local storage.

**Since last visit** finds records received or edited after the previous successfully opened panel session. It becomes available after a recorded visit. It is not Discord unread state or a decision detector. **Saved views** stores up to 20 named view/search combinations; pin and visit filters are selected separately.

**Context summary** reads the saved personal overview. Message context also offers saved conversation, channel, and server summaries. Generate/update them in the desktop app; reading them in the panel does not contact a provider. The reader shows citations, source excerpts, coverage, generation time, and corrections. It hides a summary whose evidence changed, was excluded, was removed, or lost bot access. New messages may require a desktop summary refresh.

**Clear connection** and **Change connection** both clear the saved URL and revoke local-site permission. Displayed messages and search text are cleared immediately, including when a request is still running. If the browser cannot clear stored access, the panel explains how to remove it in browser settings. Display preferences remain saved.

In message context, **Complete**, **Reopen**, **Dismiss**, priority/reply toggles, and **Snooze** change Discord Fix's local database only. Snooze offers one hour, 24 hours, or one week. Changes survive app restart and reimport. **Undo** reverses the panel's latest action if its item revision still matches. It refuses to overwrite subsequent changes. Tickets are held in memory, bounded to 500 actions, and expire when the app stops; this is not a persistent history. If a save times out, refresh and inspect the state before retrying. Preview mode disables actions and Discord links.

Keep the desktop app open. Pairing remains manual; no native-messaging host is installed. Empty-source guidance directs you to import an export or configure an authorized bot. An export primarily contains your own sent messages; a bot sees selected authorized channels and bounded history. Neither gives a complete personal inbox.

Disconnect also clears displayed context and invalidates pending responses. Preferences, pins, saved view/search text, and visit time remain saved locally. Remove the extension or clear its storage to remove them too.

## Privacy and support

Saved summaries use the source's original conversation/channel boundaries and may include topics outside a linked-reply group. The reader states this explicitly. If installing from the ZIP, extract it first and select the extracted folder with **Load unpacked**; do not select the ZIP itself.

- The extension has no Discord-site permission, content script, Discord login, or user token. It does not send or modify messages.
- The dashboard listens on this computer. It returns snapshots and accepts only explicit authenticated local follow-up actions. No bot token, provider credential, source configuration, or Discord account token is returned. Ordinary webpages receive no cross-origin access. Closing Discord Fix stops the server.
- The URL contains a temporary access token. Do not share it; clear the connection in Display settings to remove it and revoke the extension's local-site permission.
- The extension works in a normal Chrome or Edge browser. It does not run in the Discord desktop app, on mobile, or in ChatGPT's built-in browser.
- The side panel sits beside a webpage; it is not an overlay and does not change Discord's appearance or layout.

Actual extension installation, permission prompts, activation, Edge, and assistive-technology acceptance require separate verification. Script tests and rendered previews do not establish those outcomes. See [development verification](DEVELOPMENT.md).
