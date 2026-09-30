# Live Discord UI observations — 30 September 2026

## Access and method

Inspected navigation, Appearance, and Accessibility at [Discord](https://discord.com/channels/@me) in an existing logged-in Chrome session. Opening registration redirected to that session. No account was needed or created. No account preferences were changed, private message contents opened, messages sent, or account information exported. Personal names, IDs, and session credentials are absent from this report.

These are dated observations of one web session. They are not an exhaustive complaint inventory, a mobile/desktop audit, representative user research, or proof that every account sees the same experiments.

## Findings and design response

| Observed interface | Assessment | Discord Fix response |
| --- | --- | --- |
| Server rail, direct-message navigation, friend tabs, activity area, and promotional destinations coexist. Introductory/reward notices add another layer. | Navigation competes for attention; no user-outcome measurement was performed. | Six task views, exact result totals, source-linked context, and a Focus preset with fewer counters/metadata. |
| Appearance offers Light/Ash/Dark/Onyx, device appearance, and additional custom options. | A theme chooser alone adds little distinct value. | Prioritize grouping, explanations, and recoverable personal follow-ups alongside theme choices. |
| Accessibility offers text size, Compact/Default/Spacious density, message display, group spacing, saturation, contrast, role colours, reduced motion, animations, and screen-reader-related controls. | Discord already offers these accessibility preferences; they should not be called missing. | Adjustable panel text, semantic controls, visible focus, clear states, and Undo. No claim to repair Discord accessibility or certify WCAG compliance. |
| Appearance contains media/embed/thread options while font/density/contrast are in Accessibility, with category and subsection links. | Related display decisions may require movement between categories. | One Display settings area with Focus/Compact/Context presets. |

The local companion additionally offers explicit English priority rules, known thread/reply grouping with a labelled channel fallback, source coverage/freshness, and evidence-checked saved summaries. These features cannot turn incomplete source coverage into a complete inbox.

## Boundaries and validation

This extension is a companion side panel. It does not implement a reskin, DOM overlay, or hidden collection of the logged-in account's messages. UI inspection access is not a message ingestion integration.

Validate actual Chrome/Edge installation and permission recovery with synthetic data, then obtain an authorized real export or bot setup separately. Measure find/context/action/Undo journeys with willing users before claiming less overload or fewer missed messages. Assistive-technology acceptance remains open.
