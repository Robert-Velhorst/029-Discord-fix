# Discord Fix — Improvement Roadmap

Assessment date: 30 September 2026. Inspected baseline: `ebf2a203101166009cf5413679b8229c487dafe4`.

The gap table and estimates below describe the inspected baseline. Effort and impact are planning judgments, not measured user outcomes. Implementation status for the subsequent build is recorded here.

## Implementation status — extension 0.3.0

Implemented: exact result totals/pagination and full context; English rule explanations and source freshness; known thread/reply grouping with an explicit channel fallback; nonce/revision-checked local actions with Undo; saved source-linked summaries at four levels and previous-visit filtering; pins/saved searches/text sizing/presets; English manual pairing guidance; and standalone dashboard request cancellation/identity checks.

Verified with synthetic data through automated backend/script checks, the packaged Windows self-test, and Chrome interactions against real local HTTP routes. Extension APIs in the rendered preview were simulated. See `DEVELOPMENT.md` for exact evidence and limitations.

Added in 0.3.0: optional Windows native pairing with an exact extension-origin allowlist, DPAPI session record, live handshake, English recovery, and an explicit preparation/registration script. It does not install or register itself. Manual pairing remains available. Disconnect guards pending URL saves and late pairing replies; browser permission/storage changes clear obsolete displayed data.

Still open: a genuine Discord overlay, actual unpacked-extension/native-host/permission/Edge acceptance, reliable screenshot and 320-pixel reflow checks, screen-reader acceptance, authorized real-source/provider validation, measured user outcomes, and signed/store distribution. Installation confirmation is pending; native registration has not been performed. Publication/signing has not been requested. Do not treat companion progress as completion of the overlay.

## Product direction to resolve

Robert's original request was an installable, customizable shell over Discord. The current implementation is a Windows companion plus an English browser side panel. `browser-extension/manifest.json` contains no Discord host permission or content script; the panel cannot rearrange Discord's own interface. A side panel improves information presentation but does not fulfill the overlay requirement.

Keep that gap explicit. Before promising a Discord UI overlay, assess the exact proposed interaction, permissions, maintenance burden, and permitted integration route. Discord's terms restrict unauthorized software designed to modify the services and software modifications/reverse engineering, with stated exceptions. This is an integration constraint to investigate, not a claim that every possible overlay has been individually assessed. Do not obtain personal account tokens or silently broaden the current extension's access. See [Discord's terms](https://discord.com/terms) and [its self-bot policy](https://support.discord.com/hc/en-us/articles/115002192352-Automated-User-Accounts-Self-Bots).

The [integration assessment](OVERLAY-INTEGRATION-ASSESSMENT.md) now records the inspected Activity/Embedded App SDK/Social SDK routes, a bounded read-only live UI observation, and an unsent inquiry about the proposed browser presentation extension. No inspected route established permission to replace Discord's existing layout.

## Verified gaps and proposed outcomes

| Improvement | Current evidence | Proposed behavior and acceptance |
| --- | --- | --- |
| Explain every priority | `priority.py` computes reasons and the desktop detail shows them. `web_dashboard.py` omits them; the panel shows only tags. | Add an English **Why this appears** detail with rule, source, and manual override. Represent reasons as codes plus arguments rather than guessing translations of stored Dutch strings. Verify rule changes, manual overrides, deletion, and legacy data. |
| Make Everything navigable | Browser API uses `LIMIT 60`, truncates text at 420 characters, and has no paging parameters. The desktop already pages through records. | Add bounded pagination and an exact matching count. Preserve filters across pages; reset paging when filters change. Clearly label shortened previews and allow full local context. Verify over 60 matches, final/empty pages, equal timestamps, and concurrent imports without presenting the first page as the whole database. |
| Show source context for each item | Browser items include channel and author but omit server, source ID/name, import time, and coverage. Source status is a separate optional list. | Each item can reveal server/thread, source type, last successful sync/import, coverage limitations, and original link. Distinguish unavailable history from no matching messages. Verify identical channel names in different servers and imported versus connected sources. |
| Real conversation view | The browser's Conversations clause is the same as Everything. The desktop groups rows by the stored conversation field; ingestion falls back to channel identity. | Group by known thread/conversation/reply relationships, with a clearly labelled channel fallback. Show last activity, participants, open follow-ups, and expandable context. Do not invent topic boundaries or imply unavailable history was read. |
| Finish the workflow in the panel | Complete, reopen, snooze, and dismiss exist in the desktop; the panel API is GET-only. | Add explicit local workflow controls with confirmation of success and Undo. This is a deliberate change to the read-only architecture: use authenticated, narrowly scoped write operations with origin/CSRF protections and concurrency handling. No Discord message sending. Verify persistence, reimport, expiry, double clicks, and unauthorized writes. |
| Surface context summaries | Four-level summary processing and correction UI exist in desktop modules, but no summary endpoint or reader exists in the panel. | Add expandable summaries with source citations, generated time, coverage, and interpretation labels. First expose existing authorized summaries; then build **Since your last visit** using a stored visit marker and real changes. Verify corrections, exclusions, stale summaries, and unavailable evidence. |
| Simplify setup | README requires a Python desktop application, unpacked extension, copied temporary URL, and local permission grant. | Provide a first-run assistant for prerequisites, source connection/import, coverage, and first useful view. Investigate a registered native-messaging host for secure local pairing rather than scanning local ports or publishing the token. Installation of a local host remains necessary for that route. |
| Meaningful customization | The panel supports theme, density, priority counters, and source-list visibility. | Add named Focus/Compact/Context presets, adjustable text size, pinned conversations, saved filters, and controllable metadata. Expose common actions first; put advanced configuration in one clearly labelled settings area. Keep search, recovery, and original-message access discoverable. |
| Consistent browser freshness | The panel protects requests with cancellation and request identity. `dashboard.html` still drops refresh calls while pending and renders the original response. | Apply matching request identity, timeout, and filter invalidation to the standalone browser dashboard. Verify switching views/search during a delayed request and recovery from an offline server. |
| Validate the actual installation | Existing rendered checks used real synthetic HTTP snapshots but simulated extension APIs. Actual installation, side-panel activation, permission prompts, Edge, and screen-reader acceptance remain unverified. | Run the packaged extension in isolated real Chrome and Edge profiles, grant/deny/revoke local access, restart the companion, and verify reconnect. Use synthetic data first. Obtain separately authorized real-source acceptance before claiming real Discord coverage. |

## Prioritization

ICE = estimated impact × confidence in the identified need ÷ relative implementation effort. All inputs use a 1–5 scale. These figures do not estimate calendar time or prove user demand. Security and actual installation checks are release gates regardless of their score.

| Candidate | Impact | Confidence | Effort | ICE |
| --- | ---: | ---: | ---: | ---: |
| Priority explanations | 4 | 5 | 2 | 10.0 |
| Paging and full context | 4 | 5 | 2 | 10.0 |
| Per-item source context | 4 | 5 | 2 | 10.0 |
| Standalone dashboard request safety | 3 | 5 | 2 | 7.5 |
| Real conversation grouping | 5 | 4 | 3 | 6.7 |
| Guided setup and pairing | 4 | 4 | 3 | 5.3 |
| Local workflow controls in panel | 5 | 4 | 4 | 5.0 |
| Customization presets | 3 | 3 | 2 | 4.5 |
| Summary reader and change digest | 4 | 3 | 3 | 4.0 |

Recommended implementation order:

1. **Trust and completeness:** priority explanations, source context, paging/full context, and standalone dashboard request safety. The underlying information mostly exists; these changes address verified gaps in the primary browser experience.
2. **Daily workflow:** conversation grouping, panel actions with Undo, and a source-linked summary reader. Review the authenticated local write design before building action controls.
3. **Easy adoption and personalization:** first-run assistant, secure pairing, presets, saved filters, and text scaling. Assess the overlay route separately so companion progress is not presented as delivery of a Discord reskin.
4. **Release acceptance:** real packaged extension tests, accessibility review, authorized source tests, and installer/signing/distribution preparation. Publishing or obtaining paid signing capacity requires explicit authorization.

## Design basis

Use progressive disclosure: show the information needed for the current task, with source context and advanced options one clear action away. This recommendation follows [NN/G's progressive disclosure guidance](https://www.nngroup.com/articles/progressive-disclosure/). Visible state, recoverable actions, clear reasons, and consistent labels follow [its usability heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/).

Use WCAG 2.2 AA as a target for web surfaces, not a certification claim. Check keyboard-only operation, focus visibility and order, screen-reader announcements, text contrast, text resizing, and narrow-layout reflow. Reflow assessment uses the [320 CSS-pixel criterion and its exceptions](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html). [Target Size (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) specifies 24 × 24 CSS pixels or applicable exceptions; aim for larger primary action targets where space permits.

Secure automatic pairing can be explored through [Chrome native messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging), which requires a registered host and extension access configuration. It is not a way to eliminate all local installation requirements.

## Evidence needed to know it is better

There is no measured user-journey baseline yet. Before comparing versions, record these task outcomes with synthetic or explicitly authorized data:

- Install and reach the first useful view: record completion, required steps, and elapsed time. Proposed target: under five minutes after prerequisites are installed; this is a target to validate.
- Find an item that needs a response, explain why it appears, inspect its context, and open its source. Record time and incorrect selections.
- Complete or postpone an item and recover with Undo. Verify saved state after restart and reimport.
- Browse a database with more than 60 matching records and find a known older item. Compare result coverage and effort.
- Return after an absence and identify actual new decisions/actions, with valid citations. Compare summary accuracy and time-to-understanding against the current message list.
- Deny/revoke permissions or stop the local server. Verify that recovery is understandable and no obsolete response repopulates cleared data.
- Repeat essential tasks with keyboard navigation, zoom, and assistive technology. Automated checks alone do not establish accessibility.

Run maintainability and privacy checks alongside product tests. Keep interaction measurements local and voluntary; do not add covert telemetry. Observe several willing test users before claiming that the proposed features reduce overload or missed messages.

## Immediate next step

The detail flow, pagination, local workflow actions, and conversation grouping are implemented. Complete the pending actual browser installation and pairing acceptance with synthetic data, then validate authorized real sources. Resolve the documented integration route for the original shell independently; companion acceptance does not close that gap.
