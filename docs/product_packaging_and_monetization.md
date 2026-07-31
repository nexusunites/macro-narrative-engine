# MNE Product Packaging and Monetization

*Status: Ratified product definition. This document defines commercial packaging and future implementation boundaries; it does not implement authentication, billing, entitlements, metering, paid AI access, or any change to current feature behavior or access.*

## 1. Product principles

MNE monetizes research depth and workflow leverage, not basic comprehension. A free user must be able to understand the day's market narrative, why MNE reached that conclusion, and which evidence supports it. The central daily takeaway and the deterministic Explanation Layer are never hidden.

Paid plans add history, comparison, customization, automation, saved workflows, alerts, future exports, and eventually team use. Boundaries must occur where a user naturally asks to go deeper; they must not manufacture delay, obscure an available result, degrade evidence quality, or imply urgency. All plans preserve MNE's deterministic, evidence-driven character, honest empty states, presentation/engine boundary, and prohibition on trading signals or recommendations.

The commercial model has three plan families at most: Free, Pro, and a later Pro+/Team plan. Operational tooling remains an administrative concern, not a premium product. Until accounts and server-side authorization exist, these packages are definitions only: the anonymous local profile cannot identify a customer or secure a paywall, and no current access may be removed.

## 2. User segments

The willingness-to-pay assessments below are reasoned product assumptions, not findings from market research. They must be tested with real usage, interviews, conversion, retention, and cost data.

| Segment | Primary problem | Core use case | Willingness-to-pay assumption | Most valuable MNE features | Likely objections | Appropriate tier |
|---|---|---|---|---|---|---|
| Casual market follower | Market news is noisy and difficult to synthesize | Read the daily takeaway, dominant narrative, explanation, and a small evidence set | Low; likely to pay only after repeated proof that deeper context saves time | Dashboard, dominant narrative, deterministic Explanation Layer, Evidence Reader, a taste of history | “I can read news elsewhere”; infrequent use; subscription fatigue | Free |
| Active trader or investor | Needs to understand what is driving attention and whether that story is changing | Investigate a live narrative, review history, compare periods, follow narratives, and receive observed-state alerts | Moderate; $24/month is plausible if history and alerts become part of a recurring workflow | Research Workspace, Narrative History, Historical Research and Comparison, Market Context and Expression, personalization, alerts | MNE is not a signal generator; historical breadth may be incomplete; freshness and source coverage | Pro |
| Research-oriented power user | Reconstructing narrative context and maintaining continuity across periods is labor-intensive | Conduct repeated historical investigations, compare periods, save views, and use bounded AI explanation when enabled | Moderate to high; more sensitive to depth, limits, evidence transparency, and export capability than to daily-summary polish | Full historical workflow, saved views, deep evidence, comparison, AI Analyst allowance, future exports | Archive coverage, reproducibility, export availability, AI grounding, usage ceilings | Pro now; Pro+/Team later if collaboration or API access matters |
| Small team or professional workflow user | Research is fragmented across people and difficult to share or operationalize | Share investigations, saved views, alerts, reports, and structured outputs across seats | Higher organizational willingness to pay, assumed to depend on collaboration, controls, support, and reliability | Shared workspaces, shared saved views, higher limits, exports, API, multiple seats, admin controls | Security, account controls, data coverage, service expectations, procurement, and unclear ROI before team features exist | Pro+/Team later |

## 3. Free tier

Free is a useful daily market-understanding product, not a trial shell. It includes:

- The daily Dashboard, including the central market takeaway, dominant narrative, its plain-language explanation, Market Support context, and honest Data Quality context.
- Research Workspace access for the current dominant narrative and up to two additional narrative investigations per month.
- The Evidence Reader with up to five supporting evidence items per investigation when available; unavailable or incomplete evidence remains visible honestly.
- The deterministic Explanation Layer on supported surfaces with no usage charge.
- Narrative Memory summary and a 30-day Narrative History window.
- Three historical investigation views per calendar month and one Historical Comparison per calendar month, using already-completed historical artifacts.
- Following up to three narratives, saving up to two historical views, and configuring one in-app alert rule.
- Market Context and Expression summary on the daily Dashboard; instrument-level expression detail is reserved for Pro.

Free includes no exports, API access, team features, paid AI-provider calls, or user-triggered historical reconstruction. The existing deterministic AI Analyst fallback may remain visible as Explanation Layer behavior, but it is not represented as paid-provider AI. The free historical allowance is deliberately nonzero: history is MNE's strongest differentiator, and users must experience its value before a contextual upgrade prompt is meaningful.

These are future commercial boundaries. They do not retroactively restrict the current anonymous product before accounts and entitlements exist.

## 4. Pro tier

Pro is the complete individual research workflow at **$24 per month**, with an annual option of approximately **$240 per year**. It includes:

- Full Dashboard and Research Workspace access across available narratives.
- Full Evidence Reader access and complete available supporting evidence within existing product safety and display bounds.
- Narrative Memory and the full available Narrative History depth.
- Unlimited reads of completed Historical Research and Historical Comparison artifacts within a straightforward fair-use policy.
- The unified historical request workflow when that workflow is separately implemented and secured, with up to 25 user-triggered historical reconstruction requests per month.
- Full individual personalization: up to 30 followed narratives, 100 saved views, and 20 in-app alert rules.
- Full Market Context and Expression detail.
- AI Analyst access only after a real provider is approved and enabled, with 100 provider-backed questions per month. Deterministic Explanation Layer fallback keeps the experience usable when the allowance is exhausted or the provider is unavailable.
- Exports when an export product is separately implemented; exports are not part of this sprint and are not currently available.

The strongest natural upgrade triggers are reaching the free historical allowance during an investigation; needing to follow or save more narratives; needing more than one alert rule; wanting full current-versus-historical comparison depth; requesting a historical reconstruction; and, once a real provider exists, asking provider-backed AI Analyst questions. Pro never buys a different underlying conclusion or better evidence quality—it buys access, depth, continuity, and workflow capacity.

## 5. Pro+/Team tier

Pro+/Team is a later direction, not an MVP commitment. Its rough shape is a seat-based plan for small professional teams, priced when the necessary capabilities and service costs are known. Candidate capabilities are shared workspaces, shared saved views, shared alert configurations, multiple seats, higher historical-request and AI allowances, exports, API access, white-label reports, team administration, and priority support.

The tier should not launch as a larger bundle of limits alone. It becomes coherent only when accounts, organizations, roles, sharing, security controls, exports or API delivery, and support expectations are deliberately implemented. There is no committed price, seat minimum, service-level agreement, white-label scope, or launch date. MNE should not build these capabilities merely to populate a tier.

## 6. Feature entitlement matrix

Each row has an explicit disposition. “Included later” means the feature belongs to that plan once separately built; it does not claim current implementation.

| Feature | Free | Pro | Pro+/Team | Admin-only | Future |
|---|---|---|---|---|---|
| Dashboard | Included: full daily takeaway and explanation | Included | Included | No | No |
| Research Workspace | Current dominant narrative plus 2 other investigations/month | Full individual access | Full shared access | No | Plan enforcement only |
| Evidence Reader | Included, up to 5 evidence items/investigation | Full available evidence | Full available evidence | No | Plan enforcement only |
| Narrative Memory | Current summary | Full available depth | Full available depth and later sharing | No | Shared use only |
| Narrative History | 30-day window | Full available history | Full available history with shared workflows | No | Longer data depth depends on available persisted history |
| Historical Research | 3 completed-artifact views/month | Unlimited reads within fair use | Higher shared fair-use limits | No | Metering and plan enforcement |
| Historical Comparison | 1 completed comparison/month | Full access within fair use | Full shared access | No | Advanced comparison presentation and enforcement |
| Historical Requests | None | 25 user-triggered reconstructions/month once built | Larger shared allowance once built | Generation controls remain admin-only | User workflow, background execution, and metering |
| AI Analyst | Deterministic Explanation Layer only; no paid provider use | 100 provider-backed questions/month when enabled | Higher shared allowance when enabled | Provider configuration only | Real provider and metering |
| Personalization | 3 followed narratives; limited preferences | 30 followed narratives; full individual preferences | Shared and individual preferences | No | Account-backed storage and sharing |
| Alerts | 1 in-app alert rule | 20 in-app alert rules | Larger shared/custom allowance | Operational alert diagnostics only | Background evaluation and external delivery |
| Saved views | 2 historical views | 100 individual views | Larger shared library | No | Account-backed and shared storage |
| Exports | Not included | Included later for individual research exports | Included later with higher/white-label options | No | Export feature implementation |
| API | Not included | Not included | Included later with plan limits | Operational APIs remain private | Public API product and governance |
| Team features | Not included | Not included | Included later | No | Organizations, roles, sharing, and seats |
| Admin diagnostics | Not included | Not included | Not included | Permanently admin-only | Authentication and role enforcement |

## 7. Usage limits

MVP commercial limits use named constants and simple calendar-month counters. They do not require credits, rolling windows, weighted requests, dynamic pricing, or feature-specific billing ledgers.

| Limit constant | Free | Pro | Pro+/Team direction |
|---|---:|---:|---:|
| `HISTORICAL_VIEWS_PER_MONTH` | 3 | Unlimited within fair use | Larger shared fair use |
| `HISTORICAL_COMPARISONS_PER_MONTH` | 1 | Unlimited within fair use | Larger shared fair use |
| `ADDITIONAL_RESEARCH_INVESTIGATIONS_PER_MONTH` | 2 | Unlimited within fair use | Larger shared fair use |
| `FOLLOWED_NARRATIVES_MAX` | 3 | 30 | Higher shared limit |
| `SAVED_VIEWS_MAX` | 2 | 100 | Higher shared limit |
| `ALERT_RULES_MAX` | 1 | 20 | Higher shared/custom limit |
| `HISTORICAL_REQUESTS_PER_MONTH` | 0 | 25 once user requests exist | Higher shared limit |
| `AI_ANALYST_PROVIDER_CALLS_PER_MONTH` | 0 | 100 once a real provider is enabled | Higher shared limit |
| `TEAM_SEATS_MAX` | 0 | 1 | Contracted seat count |

“Unlimited within fair use” should be enforced initially through abuse protection and operational review, not opaque throttling. If real cost or abuse data later requires a numeric ceiling, changing it is a product decision that must be disclosed plainly. Monthly counters reset on the account's billing-cycle boundary for paid plans and on the first day of each calendar month in UTC for Free. Failed or rejected operations do not consume a counter; a successfully delivered result does. Read counters should count a distinct delivered view action, not asset requests or page refreshes within the same short-lived session.

## 8. Upgrade prompts

Upgrade prompts appear at natural boundaries and explain the additional value while preserving all results the user is entitled to see. They use product language, not engine internals, and never use countdowns, fake scarcity, preselected purchases, obstructive dialogs, or degraded data.

| Boundary | Placement | Value-led prompt direction | What remains visible |
|---|---|---|---|
| Historical view allowance reached | Historical selector or attempted investigation | “You used this month's 3 historical investigations. Pro includes unlimited historical investigations within fair use.” | Existing allowed investigations and the honest availability state |
| Comparison allowance reached or advanced comparison locked | Historical Comparison entry point | “Pro lets you compare periods whenever a question develops.” | The previously viewed comparison and available period descriptions |
| Follow/save limit reached | Follow or Save control | “Pro keeps up to 30 narratives and 100 saved views close at hand.” | Existing follows and saved views; removal remains available |
| Alert-rule limit reached | Preferences alert control | “Pro includes up to 20 in-app alert rules for the narratives you follow.” | Existing alert rule and alert history |
| Historical reconstruction requested | Historical request entry point, once built | “Pro includes 25 historical reconstruction requests each month.” | Available completed history and the unsubmitted request details |
| AI allowance reached | Ask Analyst panel, once provider-backed AI exists | “Your provider-backed Analyst allowance resets next month. The deterministic explanation remains available now.” | Deterministic Explanation Layer and cited persisted context |
| Export or API unavailable | Export/API action or plan information | “Team access will add structured sharing and API workflows when those products launch.” | The on-screen research result |

Prompts should be dismissible, accessible, and shown beside the boundary rather than before a user has experienced value. Repeated dismissed prompts should be rate-limited.

## 9. Pricing recommendation

Launch a paid beta at **$24/month for Pro**, with an annual option of approximately **$240/year**—about two months free. This is a starting hypothesis to revise using conversion, retention, churn, support, data, and AI-cost evidence. It is explicitly not based on market research.

| Candidate | Assessment |
|---|---|
| $19/month | Low-friction, but positions MNE as a cheap dashboard and leaves thin margin for future variable AI and historical-news archive costs. It also reduces room for a meaningful annual discount. |
| $24/month | Recommended midpoint. It is approachable before MNE has a broad brand, distinguishes Pro from a commodity dashboard, and leaves some room for future data and AI cost while preserving a later $29 test or Team upsell. |
| $29/month | Defensible from feature depth, especially with mature history and AI, but a harder opening price before brand, archive breadth, and recurring workflow value are validated. |

The paid beta should test $24 without pretending the number is permanent. Team remains seat-based and priced later. Discounts should be simple; no lifetime plan, complex add-ons, usage-credit store, or more than three tiers is recommended for MVP.

## 10. Free-to-paid journey

| Journey step | Existing MNE feature that serves it | Natural boundary or next action |
|---|---|---|
| 1. Reads the daily narrative | Dashboard, Market Support hero, dominant narrative, Data Quality summary | Opens the dominant narrative investigation |
| 2. Understands why it matters | Research Workspace, deterministic Explanation Layer, Evidence Reader | Opens Narrative History or Historical Connections |
| 3. Experiences historical value | Narrative History and one of 3 monthly Historical Research views | Requests another period or a comparison |
| 4. Builds continuity | Follow narrative, save historical view, in-app alert | Reaches the follow, save, or alert allowance |
| 5. Deepens the investigation | One monthly Historical Comparison and completed historical artifacts | Reaches a history boundary, requests reconstruction, or needs advanced comparison depth |
| 6. Receives Pro in context | Value-led prompt beside the boundary | Chooses $24 monthly or approximately $240 annual Pro |
| 7. Establishes a recurring workflow | Full history, comparison, personalization, alerts, requests, and later AI allowance | Retention depends on repeated research value, not lock-in |

The conversion mechanism is the felt value of continuity: the user can understand today for free, then discovers that Pro preserves and extends an investigation across time.

## 11. Admin-only boundaries

The following remain permanently admin-only and are never packaged as paid user features:

- Historical backfill controls and source selection.
- Replay generation controls, confirmation steps, and artifact operations.
- Historical workflow manifests and workflow state.
- Source diagnostics, Source Confidence internals, Network Health internals, raw trust and telemetry data, and quarantine recommendations.
- The Operations Center and detailed platform observability.
- Provider credentials and provider/model configuration.
- Source Registry administration and operational configuration.
- Billing administration, refunds, subscription support controls, and plan overrides.
- Raw persistence paths, internal identifiers, engine diagnostics, and security audit data.

Paid users may receive user-safe products derived from completed outputs, but payment never grants access to operational controls or raw internals. Admin access itself must be authenticated and authorized before commercial launch.

## 12. Technical entitlement architecture

This section recommends a future architecture; it does not authorize implementation.

Define a `Plan` enum with `FREE`, `PRO`, `TEAM`, and `ADMIN`. Maintain a registry of feature keys and named limit constants by plan. Route every protected server action and protected data read through one `check_entitlement(profile, feature)` chokepoint, with a separate usage-limit service for simple monthly counters. Likely modules are `mne/entitlements.py` and `mne/usage_limits.py`, integrated later with an authenticated account/profile model.

Server-side enforcement is mandatory. Hiding a link or panel is presentation behavior, not access control. Routes, form submissions, API endpoints, historical artifact reads, exports, and provider calls must all enforce plan and usage state before performing protected work. The UI consumes the same entitlement result to render available, locked, exhausted, or unavailable states in plain product language. Denials must degrade gracefully to permitted deterministic content and must not leak admin-only existence or identifiers.

Usage records need only account ID, feature key, billing period, successful-consumption count, and idempotency key. Counters increment after successful delivery and support atomic updates. Plan changes should take effect from a billing-owned subscription state, with auditable overrides reserved for admins.

The present anonymous local profile is not an identity or security boundary. Anyone with datastore access shares it, and it cannot prove who purchased a plan. Entitlements against that profile would be cosmetic and cannot secure a paywall. Authentication, accounts, sessions, authorization, profile migration, and admin-role enforcement must precede commercial entitlements.

## 13. Billing implementation sequence

1. Finalize product tiers and boundaries in this document.
2. Design and implement authentication and accounts, including identity, sessions, roles, local-profile migration, privacy, recovery, and admin protection.
3. Implement server-side entitlement checks and named usage-limit contracts without a billing provider dependency.
4. Integrate a billing provider and verified subscription lifecycle events.
5. Add plan-aware UI states and contextual upgrade paths using the server entitlement result.
6. Add simple monthly usage counters, idempotency, reset behavior, and customer-visible allowance state.
7. Test signup, purchase, renewal, failed payment, upgrade, downgrade, cancellation, refund/override behavior, and access across role and plan boundaries.
8. Launch a controlled paid beta at the ratified starting price, then measure conversion, retention, churn, support burden, and variable cost.

No Stripe or other billing-provider work belongs in this planning sprint. Authentication and account architecture is the next implementation sprint because nothing commercial is enforceable before identity and authorization exist.

## 14. Product metrics

Metrics should be calculated from MNE-owned persisted events where possible. Account-based metrics begin only after accounts exist; current local-profile activity cannot be treated as unique-user data.

| Metric | Plain formula | Purpose or source caveat |
|---|---|---|
| Daily active users (DAU) | Distinct authenticated accounts with at least one meaningful product action on a UTC day | Exclude health checks, asset loads, and admin-only actions |
| Weekly returning users | Distinct accounts active in the current 7-day window that were also active in the preceding 7-day window | Measures recurring use rather than one-time acquisition |
| Historical exploration rate | Active accounts opening at least one Historical Research or Comparison view ÷ active accounts in the period | Tests the principal differentiator and upgrade path |
| Comparison usage | Distinct successful historical comparisons ÷ active accounts in the period | Can also be segmented by Free and Pro |
| Saved narrative rate | Active accounts that follow a narrative or save a historical view ÷ active accounts in the period | Indicates workflow commitment |
| Alert engagement | Distinct alerts opened or acted on ÷ distinct alerts delivered in-app | Separate creation, delivery, open, and destination action events |
| Free-to-Pro conversion | Accounts moving from Free to paid Pro ÷ eligible active Free accounts in the period | Define eligibility consistently; do not divide by all signups forever |
| Paid churn | Paid accounts ending the period without an active paid subscription ÷ paid accounts active at period start | Report voluntary and involuntary churn separately when possible |
| AI usage when enabled | Successful provider-backed questions ÷ entitled paid active accounts; also questions per using account | Keep fallbacks, rejects, and provider failures separately visible |
| Cost per active user | Attributable data, AI, delivery, and variable infrastructure cost in the period ÷ active accounts in the period | Segment by plan and include archive scenarios when those costs exist |

Upgrade-prompt impressions, boundary hits, checkout starts, and successful purchases should form a small funnel, but prompt clicks are diagnostic—not a substitute for retention or value.

## 15. Commercial risks

| Risk | Why it matters | Mitigation or decision boundary |
|---|---|---|
| Price too low for data/API costs | Historical-news archives and a future AI provider introduce variable cost; $19 may leave inadequate margin | Start at $24, measure cost per active user, retain hard provider allowances, and revisit pricing with real cost data and the already-documented news-archive cost scenarios |
| Too much value hidden | A hard history gate prevents users from experiencing the strongest differentiator | Keep the daily takeaway, deterministic explanation, evidence, 30-day history, 3 historical views, and 1 comparison free |
| Historical-data cost or incomplete coverage | Archive breadth may be expensive while official-source reconstructions do not equal full historical market-news coverage | Preserve coverage caveats, scope requests, meter successful reconstruction, and approve archive procurement separately |
| AI-provider cost and reliability | Provider calls are variable-cost and can fail or return invalid output | Pro-only allowance, explicit invocation, bounded calls, fail-closed validation, and deterministic Explanation Layer fallback |
| Low differentiation | Users may perceive MNE as another news dashboard | Lead conversion with evidence-traceable narrative history, comparison, and continuity rather than generic summaries |
| Unclear upgrade trigger | A feature list alone does not explain why to pay | Place value-led prompts at history, save, alert, comparison, request, and AI boundaries; measure which boundaries precede conversion |
| User confusion | Tier rules can become hard to understand | Three tiers maximum, stable named limits, one allowance view, plain language, and no credit system |
| Overcomplicated tiers | Premature add-ons and Pro+ design create operational burden | Launch only Free and Pro; keep Team directional until its capabilities exist |
| Admin and security gaps | `/admin/*` currently lacks a real authenticated role boundary | Make account and admin authorization work a launch blocker; never sell admin internals |
| Anonymous local-profile limitation | The current local profile cannot identify a purchaser or enforce a paywall | State plainly that no paywall is enforceable today; implement accounts before entitlements or billing |
| Paid claims outrun implementation | Matrix entries for exports, AI, requests, API, and team use could be mistaken as available | Mark them “when enabled” or “later,” keep launch copy tied to verified behavior, and do not charge for unbuilt capability |

## 16. MVP recommendation

- **Free:** daily market understanding; the dominant narrative, deterministic explanation, and limited evidence; a 30-day Narrative History window; 3 historical investigations and 1 comparison per month; 3 followed narratives; 2 saved views; and 1 in-app alert rule.
- **Pro — $24/month or approximately $240/year:** full individual Research Workspace, Evidence Reader, available Narrative History, Historical Research and Comparison within fair use, up to 25 historical requests when built, full individual personalization and alerts, full Market Context and Expression, and 100 provider-backed AI Analyst questions per month when a real provider is enabled.
- **Team — later:** shared workflows, exports, API access, multiple seats, higher shared limits, and team controls; seat-based pricing is defined when the product exists.

Launch Free and Pro only after accounts, server-side entitlements, billing, usage counters, and lifecycle testing are complete. Preserve all current access until those implementation sprints explicitly introduce verified plan behavior.

## 17. Open questions

The following are intentionally unratified implementation or validation questions. None blocks this planning document, and none should be answered silently during implementation:

1. What account model, session strategy, recovery flow, and deployment topology will replace or migrate the anonymous local profile?
2. What event schema and privacy policy define a meaningful product action for account-level metrics?
3. Should paid-plan usage reset on an account-specific billing boundary or a unified UTC calendar month if the selected billing provider complicates reconciliation?
4. What exact short-session deduplication rule prevents refreshes from consuming historical-view allowances?
5. What constitutes fair use for unlimited completed-artifact reads, and what evidence would justify introducing a numeric ceiling?
6. Which historical reconstruction requests are operationally safe for users, and what queueing, cancellation, cost, and partial-failure behavior is required?
7. Which AI provider/model, per-call budget, and observed response quality justify enabling the 100-question Pro allowance?
8. What export formats belong in Pro versus Team, and what licensing restrictions apply to evidence or source content?
9. What archive coverage and cost scenario is commercially viable without overstating historical completeness?
10. Which Team capabilities are required before seat-based pricing is credible, and what security or support commitments accompany them?

## 18. Next implementation sprint

The next implementation sprint is **Authentication and Account Architecture**. Its handoff should define, before code is written:

- Account identity, signup, login, logout, session, verification, recovery, and deletion boundaries.
- Authorization roles for user and admin surfaces, including immediate protection of `/admin/*` and operational actions.
- Migration or linking of the anonymous local preference profile without silent data loss or cross-user leakage.
- Account-backed storage boundaries for follows, saved views, alerts, and future usage counters.
- Security controls, secrets handling, CSRF/session protections, audit events, privacy disclosure, and deployment assumptions.
- A billing-provider-neutral subscription/plan reference that entitlements can consume later, without implementing billing in the authentication sprint unless separately ratified.
- Verification for anonymous, authenticated Free, future paid, and Admin roles, including honest degraded and migration states.

Only after that sprint is verified should MNE implement the entitlement chokepoint and usage-limit model, then billing-provider integration. No authentication, billing, entitlement, AI-provider, or feature-gating code is authorized by this document.
