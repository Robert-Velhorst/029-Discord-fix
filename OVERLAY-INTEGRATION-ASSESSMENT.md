# Discord overlay integration assessment

Reviewed on 30 September 2026 against Discord's public documentation and the extension 0.3.0 source.

## Requested outcome and current delivery

The requested product is an installable extension that lets people customize Discord's existing interface: navigation, layout, information density, and visibility. The current English extension presents authorized local information in a separate browser side panel. It does not change Discord's interface. This remains a product gap, even when all companion tests pass.

## Routes assessed

| Route | Documented capability | Fit for the requested shell |
| --- | --- | --- |
| Discord Activities | An application's own web interface runs in an iframe inside Discord. | Could host a dashboard, but is not documented as a way to replace Discord's surrounding navigation or message layout. [Activities overview](https://docs.discord.com/developers/activities/overview) |
| Embedded App SDK | Activity commands expose selected integration functions. `setConfig` configures interactive picture-in-picture behavior. | The inspected command list and configuration type do not provide a host-page CSS or navigation-replacement hook. This is a conclusion about the inspected reference, not every possible private integration. [SDK reference](https://docs.discord.com/developers/developer-tools/embedded-app-sdk) |
| Discord Social SDK | Integrates Discord social features into a game's own interface. | It does not document changing Discord's existing client layout. Introducing a game integration would change this product's scope. [Social SDK overview](https://docs.discord.com/developers/discord-social-sdk/overview) |
| Current companion | This repository uses personal exports or selected authorized bot channels, then presents the local database in a browser panel. | Works for available information and local follow-ups. No Discord content script or host permission exists in the current manifest. It does not provide a complete personal inbox or an overlay. [Extension guide](BROWSER-EXTENSION.md) |
| Browser presentation extension | A proposed extension could alter the visible Discord webpage. | No permission for this particular approach was established by this review. Exact behavior and authorization need resolution before implementation under the current product specification. |

Discord's terms restrict software/service modifications and unauthorized software designed to modify its services, with stated exceptions. That is relevant to the proposed presentation extension. It is not an individual assessment of every accessibility aid or overlay, nor a legal conclusion that all such tools are prohibited. [Terms of Service](https://discord.com/terms)

The recommendation is to obtain an answer about the exact proposed presentation extension, rather than treating an Activity, SDK, or side panel as equivalent delivery. The current [product specification](PRODUCT-SPECIFICATION.md) requires a supported and authorized route for client-level UI integration.

## Account and live inspection evidence

Opening Discord's registration page in the available Chrome session redirected to the authenticated Friends page. No new account was created, no credentials were entered, and account ownership was not verified. Read-only observation found several competing navigation areas, promotional destinations, a resizable sidebar, and a central friends view. This single page is not evidence that every Discord UI problem has been inspected. No private conversation was opened; no account, privacy, or voice settings were changed. Private profile/contact details and the page screenshot are not included here.

Social SDK provisional accounts are scoped to a game's authentication and social features. Discord describes them as working only with that game and being mergeable into a full account. They are not a documented substitute for registering an account to use Discord's normal client. [Provisional accounts](https://docs.discord.com/developers/discord-social-sdk/development-guides/provisional-accounts/overview)

## Submitted authorization inquiry — response pending

Discord Developer Support received [ticket #68755960](https://support-dev.discord.com/hc/nl/requests/68755960) on 1 October 2026. The signed-in ticket page displayed “Uw aanvraag is verzonden,” the submitted English inquiry, and status **Open**. It was submitted under **Developer Compliance > Other**, whose displayed description includes questions about developer terms and policies. No application ID was provided because this inquiry concerns a proposed browser presentation extension. Submission and account activation do not establish Discord's approval of the proposed integration.

The support account was registered with the owner's authorization; the owner completed the password setup. The subsequent signed-in support page was verified before submitting the authorized inquiry. Account credentials, activation links, and private contact details are excluded from this repository. This support account is separate from a normal Discord client account.

### Follow-up record

- **1 October 2026:** Inquiry submitted and receipt verified. Last processed event: the owner's initial inquiry. No substantive Discord response or authorization has been received in the verified ticket state.
- **1 October 2026:** A follow-up was activated in the existing Codex chat, initially hourly. At the owner's subsequent request, its interval was changed to **once every 48 hours**. It checks this ticket and its corresponding email replies, continues routine correspondence, and processes new information into the product. It reports meaningful changes or required owner actions and remains quiet when there is no actionable change. Intermediate goal continuations must not trigger additional ticket or mailbox checks merely to repeat the unchanged status. Checks depend on the app's scheduler and available account access; the 48-hour schedule is not an instant notification guarantee.
- **1 October 2026, 13:25:18 and 13:25:22 CEST:** Both corresponding emails were read in full. Their `Auto-Submitted: auto-generated` headers identify them as automatic messages. Developer Compliance acknowledges receipt and says the information will be reviewed; the second email confirms receipt and suggests historical policy articles. Neither answers the presentation-extension question or grants permission. Both receipt messages are processed; no follow-up reply was sent. The second email warns that its suggested-article links can automatically close this ticket. Do not open the token-bearing automatic-answer or solve links as research navigation. If the referenced articles need review, use their ordinary public pages and verify that the version applies. No email authentication or action tokens are recorded here.
- On each meaningful response, add a dated entry identifying the response processed, its implications, and any reply or implementation completed. Avoid duplicate replies. An acknowledgement does not establish permission. Implementation of the requested shell still requires resolving the supported and authorized route in the product specification.

> We are developing Discord Fix, a local browser accessibility and focus tool. Its existing companion presents information from user-provided exports or administrator-authorized bot channels.
>
> We would like to assess a separate optional extension that changes only the presentation of Discord's web interface: text size, spacing, visibility of nonessential panels, and navigation layout. The proposed presentation layer would not obtain user tokens, call undocumented endpoints, scrape or retain message content, automate account actions, or send messages. Users would explicitly enable it and could restore the original presentation.
>
> Does Discord authorize this exact kind of local presentation extension? Is there a supported integration hook or approval process for it? Please clarify permitted behavior and any restrictions before we implement or distribute it.

## Remaining acceptance

English extension copy, backend behavior, and script checks have been verified as recorded in [DEVELOPMENT.md](DEVELOPMENT.md). Real unpacked-extension installation, browser permission prompts, native-host registration/launch, Edge, assistive technology, and real authorized sources still need acceptance. The pending browser-installation confirmation is separate from Discord authorization. Neither has been established by a rendered preview or protocol test.
