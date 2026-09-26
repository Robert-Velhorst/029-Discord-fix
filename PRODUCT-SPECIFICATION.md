# Discord Fix — Product Specification

> Detailed product direction and requirements. For the currently implemented release, setup steps, and verified limits, see [README.md](README.md).

## Product vision

Discord Fix should provide a calmer, more coherent workspace around information the user has made available through supported sources, while preserving their existing Discord account, communities, and conversations.

The product combines two ideas:

1. A personal communication dashboard that groups available conversations by attention and follow-up.
2. A companion experience beside Discord, with source-linked context and user-controlled presentation.

The first supported platform should be Windows desktop. Mobile clients may follow after the desktop product and data model are stable.

## Target audience

Discord Fix is intended for anyone who finds Discord confusing, fragmented, noisy, or time-consuming. It is not limited to a clinical or accessibility-specific audience, although accessibility and resistance to information overload are core design principles.

## Problem statement

Discord distributes communication across:

- servers and server categories;
- text, announcement, forum, and other channel types;
- threads and forum posts;
- direct and group messages;
- mentions, replies, reactions, and notifications;
- unread indicators that do not necessarily reflect importance;
- conversations that require a response but have no persistent task state.

Users can therefore lose track of:

- important new information;
- conversations they need to answer;
- decisions and commitments;
- open questions;
- the relationship between messages in different locations;
- what happened while they were absent;
- which notifications are useful and which are noise.

Discord Fix must turn this fragmented information into a small number of understandable, actionable views.

## Core experience

The application opens on a personal dashboard, not on a server list.

The dashboard contains five primary views:

### Important Now

Shows urgent or highly relevant communication across all available sources. Every prioritized item must explain why it appears here.

### Needs Reply

Shows messages and conversations that probably require a response, decision, confirmation, or other action. Users can confirm, correct, postpone, or dismiss the detected state.

### Conversations

Groups related messages into coherent conversations or topics instead of treating every message as an isolated event.

### Later

Contains items deliberately postponed by the user. Postponed items return at the chosen time or when a relevant condition changes.

### Everything

Provides a complete chronological control view of all information available to Discord Fix. It prevents AI prioritization or filtering from becoming a hidden black box.

Each item must retain:

- its original author and timestamp;
- its server, channel, thread, or direct-message context;
- a link to the original Discord message where possible;
- its source type and freshness;
- the reason for its priority or action status;
- controls to mark it complete, postpone it, correct its classification, or open the full context.

## Prioritization model

Prioritization must use a transparent hybrid model:

1. **Deterministic rules** for direct messages, mentions, replies, selected people, selected servers, and explicit deadlines.
2. **User preferences** for important people, communities, channels, topics, and notification behavior.
3. **Optional AI assistance** for relevance detection, categorization, summarization, and action recognition.

AI must not silently overrule explicit user settings. The interface must make it possible to understand and correct every important classification.

## Continuous Context Summary

A defining feature of Discord Fix is a continuously maintained summary of complete conversations.

The system should update summaries approximately once per hour when new relevant activity exists. Users can also request an immediate refresh. Quiet conversations should not be processed unnecessarily, and the refresh interval may be configured per source.

The feature is separate from the ordinary inbox so that AI-generated text does not create additional clutter.

### Summary hierarchy

Summaries exist at four levels:

1. conversation or thread;
2. channel;
3. server;
4. personal overview across all available Discord communication.

Higher-level summaries are derived from lower-level context and must link back through the hierarchy to original source messages.

### Required summary structure

Where applicable, a summary should identify:

- topics discussed;
- important facts and developments;
- decisions made;
- open questions;
- requested or promised actions;
- responsible people and stated deadlines;
- disagreement, uncertainty, or unresolved interpretations;
- what changed since the previous summary;
- source links for verification.

The UI must distinguish source-backed facts from AI inference. Unsupported certainty is unacceptable.

### Incremental processing

The system should normally update an existing structured summary with new messages instead of reprocessing the entire history every hour. Periodic full reconciliation should detect accumulated distortion, missing context, or outdated conclusions.

## Privacy model

Discord Fix must be local-first and privacy-conscious.

- Raw imported messages, indexes, preferences, and personal states are stored locally by default.
- Users may choose local AI or an external AI provider.
- External processing is opt-in and must clearly identify what data will leave the device.
- AI processing can be disabled per server, channel, thread, conversation, or supported message.
- Excluded content must not leak into higher-level summaries.
- Personal summaries are private by default.
- Shared server summaries are a separate, explicitly enabled feature and may only expose information the viewer is authorized to access.
- Secrets and authentication tokens must use operating-system secure storage.
- The product must support deletion, export, retention controls, and provider-specific data-handling disclosures.

Privacy, data protection, and consent requirements must be reviewed before any public deployment, particularly for server-wide AI processing.

## Discord access constraints

Discord Fix must not use:

- normal user account tokens;
- self-bots or automated normal user accounts;
- unauthorized scraping;
- reverse engineering of private Discord interfaces;
- software that modifies the official Discord service without authorization;
- any integration that creates a material risk of account termination.

Relevant official references:

- [Discord: Automated User Accounts (Self-Bots)](https://support.discord.com/hc/en-us/articles/115002192352-Automated-User-Accounts-Self-Bots)
- [Discord: Platform Manipulation Policy Explainer](https://discord.com/safety/platform-manipulation-policy-explainer)
- [Discord Terms of Service](https://discord.com/terms)
- [Discord Social SDK](https://discord.com/developers/docs/social-sdk/index.html)

All Discord integrations must use officially permitted APIs, SDKs, OAuth flows, bots, applications, exports, or written authorization.

## Delivery strategy

### Phase 1: Discord Fix Companion

Build a useful, policy-compliant Windows desktop companion without pretending that it has universal live access.

Supported inputs may include:

- an official Discord application or bot installed by a server administrator;
- live events and history available to that application within its granted permissions;
- voluntary imports of user-provided Discord data exports;
- officially authorized SDK access where available.

The application must clearly label data as:

- **Live** — received through an authorized active integration;
- **Imported** — obtained from a user-provided export, with the import date;
- **Unavailable** — outside the application's current permissions or official access.

Phase 1 users can:

- review the five dashboard views;
- search and filter available communication;
- read hierarchical continuous summaries;
- inspect decisions, open questions, and action items;
- mark items complete;
- postpone items;
- correct AI classifications;
- follow a deep link to the original Discord message to reply.

Writing or replying through Discord Fix is outside the initial scope unless an official interface explicitly permits it.

### Phase 2: Enhanced official integration

If Discord grants broader communication access:

- add authorized in-app replies;
- improve live coverage of direct messages, threads, and servers;
- reduce dependence on server-by-server bot installation;
- synchronize read, reply, and completion state where officially supported.

### Phase 3: Client-level integration only with authorization

Only explore a Discord client replacement or client-level UI integration if Discord explicitly supports and authorizes that specific approach. Do not implement an injected overlay, reskin, or layout modification as a workaround. If no authorized route exists, Discord Fix remains a separate companion. Mobile companion applications may follow after the desktop architecture and interaction model are proven.

## Phase 1 functional requirements

### Source management

- Connect and disconnect authorized Discord applications or SDK integrations.
- Import supported Discord data packages.
- Show permissions and coverage for every source.
- Never represent imported data as live.
- Detect revoked access and communicate the impact clearly.

### Unified communication model

Normalize supported Discord data into stable internal entities:

- source;
- server;
- channel;
- thread or topic;
- conversation;
- participant;
- message;
- reference or reply;
- summary;
- decision;
- open question;
- action item;
- user state;
- source freshness and permission state.

Original Discord identifiers must be retained for traceability and deep links.

### Dashboard and workflow

- Implement all five dashboard views.
- Allow manual priority and importance overrides.
- Support complete, reopen, postpone, and dismiss actions.
- Preserve user workflow states locally even when Discord provides no equivalent state.
- Provide full-text search over locally available content.
- Offer a calm focus mode that hides nonessential navigation and metadata.

### AI processing

- Support pluggable AI providers rather than coupling the product to one vendor.
- Provide a local-AI interface even if initial model support is limited.
- Run deterministic extraction before generative summarization where practical.
- Store structured summary output, citations, source ranges, version, model, and processing time.
- Recompute affected higher-level summaries when lower-level summaries materially change.
- Allow users to disable, refresh, correct, or delete summaries.
- Never automatically send messages or take external actions based solely on AI inference.

### Notifications

Notifications must represent useful changes, not mirror Discord's notification volume.

Examples include:

- a new high-priority item;
- an approaching explicit deadline;
- a postponed item returning;
- a material change to an existing summary;
- revoked access that makes a source stale.

Users must be able to understand and configure every notification type.

## Suggested architecture

Keep components isolated behind explicit interfaces:

1. **Desktop shell and user interface** — dashboard, inbox, summaries, search, settings, and deep links.
2. **Connector layer** — official Discord bot/API/SDK integrations and import adapters.
3. **Normalization layer** — converts source-specific payloads into the unified communication model.
4. **Local data layer** — encrypted or access-controlled storage, indexes, workflow state, summaries, and audit metadata.
5. **Priority engine** — deterministic rules, user preferences, and optional AI scoring.
6. **Summary engine** — incremental hierarchical summaries, reconciliation, citations, and correction history.
7. **Scheduler** — adaptive hourly processing, retries, postponements, and refresh requests.
8. **Privacy and policy guard** — exclusions, consent, retention, provider routing, and permission checks.
9. **Deep-link service** — opens the original message in Discord when supported.

No connector, AI provider, or UI component should directly own the complete product data flow. Interfaces must allow connectors and AI providers to be replaced independently.

## Data flow

1. An authorized connector receives or imports Discord data.
2. The privacy guard rejects excluded or unauthorized content.
3. The normalization layer creates or updates internal entities.
4. The local data layer records source, permission, and freshness metadata.
5. The priority engine updates dashboard placement and explains its reasoning.
6. The summary engine updates affected conversation-level summaries.
7. Material changes propagate upward to channel, server, and personal summaries.
8. The scheduler avoids work when no relevant changes occurred.
9. The UI presents results with source links, confidence, and correction controls.

## Failure handling

The application must fail visibly and safely.

- Stale or revoked sources are clearly marked.
- Failed AI processing does not remove original messages or user workflow state.
- Partial summaries are labelled incomplete.
- Rate limits use documented backoff and retry behavior.
- Imported data errors identify the affected files or records without discarding valid imports.
- Provider outages allow queued retries or switching providers.
- Unsupported Discord features are shown as unavailable rather than approximated through prohibited access.
- Users can always reach the unfiltered Everything view.

## Accessibility and interface principles

- Reduce simultaneous panels, controls, badges, and competing colors.
- Prefer one primary action per screen.
- Use consistent terms across servers, channels, threads, and messages.
- Explain unfamiliar states in plain language.
- Preserve keyboard navigation and screen-reader semantics.
- Support adjustable density, font size, contrast, motion, and notification intensity.
- Never rely on color alone to communicate state.
- Reveal complexity progressively instead of showing every Discord feature at once.

A user should be able to answer these questions within seconds:

1. What is important now?
2. What needs my response?
3. What changed while I was away?
4. What can safely wait?
5. Where did this information come from?

## Out of scope for Phase 1

- Voice and video calling.
- Screen sharing or streaming.
- Full Discord server administration.
- Reimplementation of every Discord feature.
- Automated replies or autonomous messaging.
- Universal access to servers or direct messages without official permission.
- Circumvention of Discord access controls.
- A simultaneous mobile release.
- Training foundation models on user communications.

## Testing requirements

At minimum, testing must cover:

- connector permission boundaries;
- exclusion rules at every summary level;
- correct source and freshness labels;
- normalization of representative Discord structures;
- priority-rule explanations and manual overrides;
- action-state persistence;
- summary citation integrity;
- incremental updates and full reconciliation;
- duplicate, edited, and deleted messages;
- rate limiting, revoked access, offline use, and provider failure;
- safe handling of malformed imports;
- deep links;
- keyboard navigation and essential accessibility flows;
- prevention of prohibited authentication methods.

Use synthetic or explicitly authorized test data. Private production conversations must not become general development fixtures.

## Phase 1 acceptance criteria

Phase 1 is successful when a test user can:

1. connect at least one officially authorized live source or import supported data;
2. immediately understand the coverage and freshness of that source;
3. see relevant communication in the five dashboard views;
4. identify why an item is important or needs a reply;
5. read a source-linked summary at conversation, channel, server, and personal level;
6. distinguish facts, decisions, open questions, actions, and AI inference;
7. correct a classification or summary;
8. complete or postpone an item;
9. open the original Discord message;
10. exclude selected content from all AI processing;
11. recover safely from a disconnected source or failed AI provider.

## Product success measures

Evaluate whether Discord Fix reduces:

- time required to become current after an absence;
- number of important messages missed;
- time spent navigating between Discord locations;
- uncertainty about what requires a response;
- unnecessary notifications and repeated rereading.

Also measure user trust through correction frequency, source-link usage, summary accuracy feedback, and continued use of the dashboard.

## Development rule

Do not optimize for feature parity with Discord. Optimize for clarity, traceability, user control, and minimum time-to-understanding.

When Discord's current access rules prevent a desired feature, document the limitation and preserve a compliant extension point. Do not silently replace the feature with a prohibited workaround.
