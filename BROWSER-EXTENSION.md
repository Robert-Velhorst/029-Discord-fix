# Discord Fix browser side panel for Chrome and Edge

The Discord Fix extension displays your local Discord Fix dashboard in a browser side panel next to the current page. It does not read or modify Discord pages. It connects only to the read-only dashboard served by the Discord Fix desktop app on your computer.

The extension does not need access to Discord. When you connect a dashboard URL, the browser asks for optional access to `http://127.0.0.1/*`. The URL contains a temporary random access token and is stored in the extension's local browser storage. Keep it private.

The browser permission technically covers HTTP ports on `127.0.0.1`. The extension validates that the URL uses that loopback address and contains exactly one token path. It makes read-only GET requests without credentials and rejects redirects. **Clear connection** removes the saved URL and revokes the local-site permission.

## Install the development extension

The extension has not been published to the Chrome Web Store or Microsoft Edge Add-ons. Load it unpacked for local testing:

1. Start Discord Fix on Windows and select **Browserdashboard** (the Dutch option for opening the browser dashboard). Keep the app open.
2. Copy the complete `http://127.0.0.1:...` URL from the address bar.
3. Open `chrome://extensions` in Chrome or `edge://extensions` in Edge and turn on **Developer mode**.
4. Select **Load unpacked** and choose this repository's `browser-extension` folder.
5. Open the Discord Fix side panel using the extension's toolbar icon. Paste the local dashboard URL, select **Connect**, and grant the requested local-site permission.

The panel refreshes the dashboard about every 30 seconds while Discord Fix is running. If you close and later restart Discord Fix, select **Browserdashboard** again and connect using the new URL; the old URL expires when the app closes.

## Use the side panel

Choose among Overview, Important, Needs reply, Conversations, Later, and Everything. Search the information already available in Discord Fix. A message's **Open original in Discord** link opens that message in a new browser tab when a valid Discord link is available.

Use **Display settings** to choose a dark, light, or system theme; comfortable or compact rows; priority counts; and source-status visibility. These preferences are stored in the browser's local extension storage. Source-status labels and dates are displayed in English. Message text, channel names, and author names remain as provided by their source.

The side panel is read-only. Change priorities and follow-up states in the Discord Fix desktop app. Keep that app open while using the local dashboard.

## Privacy and support

- The extension has no Discord-site permission, content script, Discord login, or user token. It does not send or modify messages.
- The local dashboard listens on this computer and returns read-only data. Closing Discord Fix stops the dashboard server.
- The URL contains a temporary access token. Do not share it; clear the connection in Display settings to remove it and revoke the extension's local-site permission.
- The extension works in a normal Chrome or Edge browser. It does not run in the Discord desktop app, on mobile, or in ChatGPT's built-in browser.
- The side panel sits beside a webpage; it is not an overlay and does not change Discord's appearance or layout.
