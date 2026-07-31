# Historical News-Archive Feasibility and Provider Selection

**Status:** Feasibility study — complete. Research and architecture only. No connector implemented, no provider signed, no data purchased.
**Implementation posture:** **Blocked / Deferred.** A preferred paid-provider candidate has been identified, but implementation is deferred pending budget availability and written confirmation of commercial storage and display rights. Existing official-source historical reconstruction (Fed/FOMC, BLS CPI, BEA GDP/PCE, EIA Energy) remains the supported production path.
**Research date:** 2026-07-31. Provider facts verified against sources cited inline; labels: **[CONFIRMED]** (from provider documentation/pricing pages), **[ASSUMPTION]**, **[ESTIMATE]**, **[UNKNOWN — sales/legal contact required]**.
**Not legal advice.** Licensing interpretations below require confirmation against current provider terms before any commercial commitment.

---

## 1. Purpose

Determine the most viable historical news/archive data strategy for MNE without creating unacceptable licensing, storage, cost, compliance, or product-quality risk. MNE reconstructs official macro evidence (Fed/FOMC, BLS CPI, BEA GDP/PCE, EIA Energy) but official releases alone do not represent the broader market conversation. For historical comparison to become a strong paid feature, MNE needs broader historical narrative coverage.

## 2. Product requirement

Historical Replay must be able to reconstruct the *market conversation* — not just official releases — for supported dates, feeding the same pipeline: normalized record → evidence object → `historical_evidence/{backfill_id}` → Replay → Research/Comparison. The paid-feature bar is: honest, replay-compatible, deterministic, and affordable at 100–1,000 subscribers.

## 3. Minimum data requirement

Per ratified decision, MNE operates **headline-first**: normalized metadata + headlines; licensed snippets are an upgrade, not a dependency; no full article text stored unless explicitly licensed.

Minimum fields per historical news record: headline/title; source/publication; publication timestamp (UTC-normalized); canonical URL or provider reference; provider article ID; category/topic metadata (if provided); language; rights/storage classification; retrieval timestamp. Optional if licensed: snippet/summary.

**Is full text necessary?** No. MNE's live pipeline classifies on headlines today; taxonomy scoring is headline-compatible. Full text would reduce headline-only ambiguity (risk §12) but is not required for MVP-quality reconstruction. **[CONFIRMED against MNE's own architecture]**

## 4. Target historical coverage

Per ratified anchor: **2015→present primary; 2020→present fallback; 2008/2000 only with clear justification.**

Assessment: 2015→present is supported by at least two credible providers (NewsAPI.ai archive since 2014 [CONFIRMED]; Webz.io archive since 2008 [CONFIRMED per product page]; GDELT 2.0 since Feb 2015 [CONFIRMED]). It covers the 2015–16 rates/China scare, 2018 volatility, 2020 COVID, 2021–22 inflation regime, and the AI era — all taxonomy-relevant. Pre-2015 archives shift toward enterprise pricing (Factiva, LSEG) and older news formats that degrade taxonomy fit. **Recommendation: 2015→present.** Extend only if a chosen provider makes it near-free and quality holds.

## 5. Provider landscape

Categories investigated: commercial news APIs, historical news databases, event/news datasets, licensed financial-news providers, web/news archives, open datasets, first-party publisher APIs.

**NewsAPI.ai (Event Registry)** — commercial news API. Archive since 2014; 150,000+ sources, 60+ languages; article data includes title, body, URL, publication date, source; entity/category enrichment; dedup and clustering; REST + Python/Node SDKs; 99.99% uptime SLA. Pricing public and token-based: free tier 2,000 searches; 5K plan $90/month; recent search = 1 token; archive search = 5 tokens per searched year; up to 100 articles per search; overage $0.015/token; monthly plans, cancel anytime. **[CONFIRMED — newsapi.ai/plans, accessed 2026-07-31]** Storage/caching/retention rights for retrieved metadata and headlines: **[UNKNOWN — terms of service review + written confirmation required]**.

**GDELT** — open event/news dataset. All GDELT datasets are stated as available for unrestricted academic, commercial, or governmental use without fee; event backfile to 1979; GDELT 2.0 (news-level, richer metadata) from Feb 2015; 15-minute updates; 60,000+ sources, 100+ languages. **[CONFIRMED — gdeltproject.org]** Caveats: GDELT provides metadata, URLs, tone, and themes — not licensed headlines/snippets verbatim in all products; article titles are present in some tables. Data-quality noise and non-market topic breadth are real. Rights to *display* third-party headlines sourced via GDELT: **[UNKNOWN — the open license covers GDELT's data, not underlying publisher content]**.

**Webz.io** — commercial news API + archive. Historical data to January 2008 including full text; consumption-based pricing (pay per result); historical access carries a premium. **[CONFIRMED — webz.io product pages]** Actual prices, storage/display rights: **[UNKNOWN — sales contact]**.

**NewsCatcher** — commercial news API, 70,000+ sources, dedup/clustering/enrichment. Entry tiers reportedly from ~$29/month; enterprise ~$10k/month; republishing rights are enterprise-only and negotiated. **[ESTIMATE/third-party — datarade/comparison sources; official pricing partly gated]** Archive depth: **[UNKNOWN]**.

**Quantexa News API (ex-Aylien)** — licensed news intelligence. 8+ year archive, ~400M enriched articles, 90,000+ sources. **[CONFIRMED — aylien.com/docs]** Direct self-serve signup currently unavailable; pricing opaque, enterprise-oriented. **[CONFIRMED as of research date]**

**Dow Jones Factiva / DNA (Snapshots & Streams)** — licensed financial-news database; deep multi-decade archive; strong rights framework; API access via Dow Jones Developer Platform. Pricing is enterprise/negotiated and varies by content breadth and archive depth. **[CONFIRMED existence; pricing UNKNOWN — sales]** Likely the long-term "serious" option; almost certainly premature at MNE's current stage. **[ASSUMPTION]**

**LSEG/Refinitiv, Bloomberg, RavenPack** — enterprise financial news/analytics archives. Enterprise pricing, procurement-heavy. **[ASSUMPTION based on market positioning; no public pricing]** Tier C for now on cost, not quality.

**Finnhub / Polygon(Massive)+Benzinga / Tiingo / Marketaux** — market-data APIs with company-news endpoints. Useful for ticker-scoped news; archives generally shallower, terms typically restrict redistribution/display; per-source news breadth narrower than general news APIs. **[ASSUMPTION — verify per provider if ticker-scoped supplements are ever needed]**

**Mediastack / NewsData.io** — budget aggregators. Mediastack from ~$24.99/month, ~7,500 sources, historical access on higher tiers; NewsData.io 97,000+ sources, historical access on paid tiers, free tier permits commercial use. **[CONFIRMED via pricing pages/comparison content; details to verify]** Viable budget fallbacks; enrichment and archive depth weaker than NewsAPI.ai.

**Common Crawl News (CC-NEWS)** — open crawl archive from 2016; WARC files by month; but Common Crawl explicitly cannot license the crawled page contents — copyright remains with publishers; US fair-use distribution. **[CONFIRMED — commoncrawl.org, community forum]** Using it in a paid product for display is legally unclear. Research-only.

**First-party publisher APIs** — NYT Archive API: terms forbid commercial use **[CONFIRMED via multiple sources; re-verify current terms]**. Guardian Open Platform: historically commercial-friendly, but available sourcing is dated (2009-era); current commercial tiers **[UNKNOWN — verify]**. Either way: single-publisher breadth is too narrow to carry MNE's narrative reconstruction; at most a supplement.

**Internet Archive** — publishers are actively limiting access over AI-scraping concerns (reported Jan 2026); no commercial content license. Research-only.

Sources: [newsapi.ai/plans](https://newsapi.ai/plans), [newsapi.ai/about](https://newsapi.ai/about), [gdeltproject.org/about](https://www.gdeltproject.org/about.html), [GDELT on AWS Open Data](https://registry.opendata.aws/gdelt/), [webz.io News API](https://webz.io/products/news-api/), [webz.io Archived Data](https://webz.io/products/archived-data/), [newscatcherapi.com](https://www.newscatcherapi.com/), [NewsCatcher on Datarade](https://datarade.ai/data-providers/newscatcher-api/profile), [aylien.com](https://aylien.com/), [docs.aylien.com](https://docs.aylien.com/newsapi/v6/getting-started/), [Dow Jones factiva-news-python](https://github.com/dowjones/factiva-news-python), [Vendr Dow Jones pricing](https://www.vendr.com/marketplace/dow-jones), [CC-NEWS dataset](https://data.commoncrawl.org/crawl-data/CC-NEWS/index.html), [Common Crawl blog](https://commoncrawl.org/blog/news-dataset-available), [mediastack pricing](https://mediastack.com/pricing), [marketaux pricing](https://www.marketaux.com/pricing), [NewsData.io comparison](https://newsdata.io/blog/best-news-api-comparison-2/), [Nieman Lab on Internet Archive limits](https://www.niemanlab.org/2026/01/news-publishers-limit-internet-archive-access-due-to-ai-scraping-concerns/).

## 6. Provider comparison matrix

| Provider | Archive | Breadth | Headline/snippet/full-text | Access | Pricing | Storage/display rights | Commercial use | Reliability risk | Integration | MNE fit |
|---|---|---|---|---|---|---|---|---|---|---|
| NewsAPI.ai | 2014→ [C] | 150k+ sources [C] | All incl. full body [C] | REST/SDK [C] | $90/mo 5K + tokens, public [C] | UNKNOWN — confirm | Yes (commercial plans) [C] | Low–moderate | Low | **Strong** |
| GDELT | 2015→ (2.0) [C] | 60k+ sources [C] | Metadata/URL/themes; titles partial [C] | Free bulk/BigQuery [C] | $0 [C] | GDELT data open; publisher headlines UNKNOWN | GDELT: yes [C] | Moderate (quality noise) | Moderate | Supplement/prototype |
| Webz.io | 2008→ [C] | Large [C] | Full text [C] | API [C] | Consumption; UNKNOWN amounts | UNKNOWN | Yes [C] | Moderate | Moderate | Candidate — sales contact |
| NewsCatcher | UNKNOWN | 70k+ [C] | Full metadata [C] | API [C] | ~$29→$10k/mo [E] | Enterprise-negotiated [C] | Yes | Moderate | Low | Candidate — verify archive |
| Quantexa (Aylien) | 8+ yrs [C] | 90k+ [C] | Enriched full [C] | API [C] | Opaque/enterprise [C] | UNKNOWN | Yes | Moderate (post-acquisition access) | Moderate | Later stage |
| Factiva/DNA | Decades [C] | Premium licensed [C] | Full, licensed [C] | Snapshots/Streams [C] | Enterprise UNKNOWN | Strong, contractual | Yes | Low | High | Long-term upgrade |
| LSEG/Bloomberg/RavenPack | Deep [A] | Premium | Full | Enterprise | Enterprise [A] | Contractual | Yes | Low | High | Not now (cost) |
| Mediastack/NewsData.io | Tier-gated [C] | 7.5k/97k+ [C] | Headline+desc [C] | API [C] | $25–$200/mo [C] | Verify | Yes (incl. free tier at NewsData.io) [C] | Moderate | Low | Budget fallback |
| CC-NEWS | 2016→ [C] | ~1k+ sites [C] | Full WARC [C] | Free bulk [C] | $0 | **No content license** [C] | Fair-use only [C] | High (legal) | High | Research-only |
| NYT/Guardian APIs | Deep [C] | Single publisher | Varies | API | Free/UNKNOWN | Publisher terms | NYT: no [C]; Guardian: verify | Low | Low | Too narrow |
| Internet Archive | Deep | Broad | Full | Bulk | $0 | None; access shrinking [C] | No | High | High | Research-only |

[C]=confirmed, [A]=assumption, [E]=estimate.

## 7. Provider tiers

- **Tier A (commercially viable for early paid MNE):** NewsAPI.ai (pending terms confirmation); Webz.io and NewsCatcher (pending sales-confirmed pricing and rights).
- **Tier B (prototyping / limited launch):** GDELT (free, open, quality-noisy; publisher-headline display rights need care); Mediastack / NewsData.io (budget, shallower enrichment).
- **Tier C (research-only / unsuitable now):** Common Crawl News, Internet Archive (no content license); NYT API (non-commercial); Bloomberg/LSEG/RavenPack/Factiva (enterprise cost — Factiva graduates to Tier A at scale); Quantexa (opaque access).

## 8. Recommended provider strategy

**Preferred candidate (deferred): NewsAPI.ai as the single historical news provider, layered on MNE's existing official connectors.** NewsAPI.ai is the preferred paid-provider candidate based on this research, but **no subscription or connector implementation is recommended now** — current budget does not support the API subscription, and written commercial storage/display rights confirmation is outstanding. The four official historical sources (Fed/FOMC, BLS CPI, BEA GDP/PCE, EIA Energy) remain MNE's active historical coverage. Legally unclear substitutes (Common Crawl content, GDELT-sourced publisher headlines for display, publisher APIs prohibiting commercial use) must **not** be used as free stand-ins.

Rationale: it is the only researched provider combining a confirmed 2014→present archive, confirmed public self-serve pricing that fits MNE's stage ($90/month + metered archive tokens), broad source coverage, built-in dedup/clustering (directly mitigating §12 risks), and monthly cancellability (low commitment risk). Official connectors remain the provenance backbone; news evidence adds conversation breadth.

Trade-offs: single-provider concentration (mitigated by Provider Independence measurement, not symmetry — concentration is recorded, not hidden); storage/display rights unconfirmed (gating condition, §15); enrichment taxonomies are provider-specific (MNE classifies with its own taxonomy on headlines, so dependency is shallow). Rejected alternatives: multi-provider dedup (premature complexity); open-data-first GDELT MVP (weaker headline licensing story for a *paid* feature, higher quality noise); "no provider yet" (economics are actually workable — see §9).

## 9. Cost scenarios

All figures are **estimates** built on NewsAPI.ai's confirmed token schedule (archive search = 5 tokens/searched-year; 100 articles/search; 5K plan $90/month; overage $0.015/token). Assumption: one historical-date reconstruction ≈ 10–20 archive searches (theme keywords × pagination), all within a single year → 50–100 tokens ≈ **$0.75–$1.50 per reconstruction-date at overage rates, less within plan**.

- **Internal testing:** free tier (2,000 searches) or one month of 5K plan. **~$0–90.**
- **Small beta (30-date MVP + iteration):** ~30 dates × 2–3 passes → 3,000–9,000 tokens; 5K plan suffices. **~$90–180/month, 1–2 months.**
- **100 paying users:** assume 5 user-requested reconstructions/user/month, 50% cache hit → ~250 new reconstructions → 12.5k–25k tokens → 5K plan + overage or a higher plan. **~$200–500/month.** Storage of headline metadata is negligible (tens of MB).
- **1,000 paying users:** ~2,500 new reconstructions/month → 125k–250k tokens → **~$2,000–4,000/month at overage rates; a negotiated volume plan should be materially cheaper [UNKNOWN — sales]**. Caching and pre-computed popular dates are the main cost lever: reconstructions are immutable once built, so marginal provider cost trends toward zero for repeated dates.

Cost-to-revenue check: at plausible subscription pricing, provider cost stays in single-digit percent of revenue in the 100-user scenario and low double digits worst-case at 1,000 users pre-negotiation. **[ESTIMATE]**

## 10. Licensing and storage model

Store (per ratified headline-first posture): normalized evidence metadata; headline; provider article ID + canonical URL; rights/storage classification per record; MNE classification results; replay artifact; retrieval timestamp; **no snippet initially; no full article body.**

Policies: retention — headline metadata retained with replay artifacts indefinitely unless provider terms mandate expiry **[gating question]**; cache — reconstructions immutable and cached permanently (subject to same terms); deletion — support per-provider takedown by article ID; attribution — publication name displayed with every evidence item, provider attribution per contract; audit — provenance chain (provider → request → record → evidence → replay) persisted per MNE's explainable-provenance standard; display — headlines shown as attributed links, never full text, consistent with widespread aggregator practice but **to be confirmed in NewsAPI.ai's terms before launch**.

## 11. Backfill integration architecture

```
NewsAPI.ai archive
  → news_archive connector (new, one of N historical connectors)
  → normalized historical record (headline-first schema, §3)
  → evidence object (+ rights_classification field — additive)
  → historical_evidence/{backfill_id}
  → Historical Replay → Historical Research / Comparison
```

Fit: **additive.** The existing Historical Evidence Backfill Architecture already supports multi-source connectors (Fed/BLS/BEA/EIA); a news connector is one more provider behind the same normalized-record contract. Required changes flagged (not designed here): (1) a `rights_classification` field on evidence records; (2) Coverage Intelligence should recognize a "news archive" source class so coverage states reflect news breadth honestly; (3) dedup at the normalized-record layer (provider clustering + URL/title canonicalization). No changes to Replay calculations, scoring, or taxonomy.

## 12. Quality risks

Duplicate syndication / wire duplication — mitigate with provider clustering [C: NewsAPI.ai provides] + MNE canonical-URL/title dedup; measure duplicate rate in MVP. Timestamp inconsistencies — normalize to UTC; drop records without parseable timestamps; test fixture required. Republished/updated articles — prefer earliest publication timestamp; record provider ID to detect re-crawls. Paywall truncation — irrelevant under headline-first. Source concentration / topic bias — measure with existing Provider Independence and Coverage Intelligence machinery; report, don't hide. Missing niche publications / archive gaps — surface via coverage caveats; never claim completeness. Headline-only ambiguity — accept as known limitation; snippets are the future upgrade lever. Survivorship bias — archives over-represent surviving outlets; include in user-facing limitations. Provider classification noise — ignore provider categories for scoring; MNE's own taxonomy classifies headlines.

## 13. User-facing coverage language

Approved: "Historical reconstruction uses supported archived sources." / "Coverage varies by date and provider." / "This does not represent every article published during the period." / "Historical evidence availability may differ between periods."

Never claim: complete historical news coverage; every market narrative captured; complete market history; full media consensus.

## 14. MVP recommendation

**Historical News Backfill MVP — Blocked / Deferred.** A preferred paid-provider candidate has been identified, but implementation is deferred pending budget availability and written confirmation of commercial storage and display rights. Existing official-source historical reconstruction remains the supported production path.

**Zero-cost validation path (optional, only if genuinely free):** explore the NewsAPI.ai free tier (2,000 searches) to test whether archive headlines support MNE taxonomy scoring for 3–5 historical dates. Constraints: no paid commitment; no scraping; no paywall bypass; no assumption that free access grants commercial storage/display rights; results are throwaway analysis, not stored evidence; **no production connector**.

**Deferred MVP specification (for when unblocked):**

- Provider: NewsAPI.ai (5K plan, monthly, cancellable).
- Date range: 2015-01-01 → present; MVP verification set of **30 selected dates** spanning 2015–16 rates scare, 2018 volatility, 2020 COVID, 2022 inflation, 2023–25 AI era.
- Evidence format: headline-first normalized record (§3) with `rights_classification`.
- Storage rules: §10 — headlines + metadata only, immutable cached reconstructions, per-record provenance.
- One connector: `news_archive` connector under the existing backfill architecture.
- Bounded verification period: one calendar month of testing within plan limits.
- Success criteria: 30 dates reconstructed; stable UTC timestamp handling; duplicate rate below a set threshold (propose <10% post-dedup); source breadth floor met (propose ≥15 distinct publications per reconstructed date, tuned in MVP); replay-compatible evidence verified end-to-end; licensing/storage rules confirmed **in writing**; no full-text storage.

## 15. Go/no-go criteria

**Go when all hold:** (0) budget is available for the API subscription — currently **not met (gating)**; (1) NewsAPI.ai terms confirm rights to store and display headlines + metadata with attribution — currently **UNKNOWN (gating)**; (2) cost fits subscription economics — currently **met per §9 estimates**; (3) archive coverage adequate for 2015→present — **met [C]**; (4) headline quality supports MNE taxonomy scoring — **testable in free tier before any spend**; (5) provider reliability acceptable (99.99% SLA stated [C], monitor in MVP); (6) storage/display terms workable — same as (1).

**No-go if:** commercial rights unclear after written inquiry; caching/storage of metadata disallowed; archive coverage materially gappier than documented (test in MVP); pricing at scale incompatible after volume negotiation; source diversity too narrow in practice; full text turns out to be required for acceptable scoring (contradicts current evidence); integration would depend on scraping (it does not).

## 16. Open questions

1. NewsAPI.ai terms of service: explicit written confirmation of storage, caching, retention, and headline-display rights for a commercial product (gating).
2. Whether negotiated volume pricing at the 1,000-user scale improves materially on $0.015/token overage.
3. Webz.io and NewsCatcher: actual prices, archive depth (NewsCatcher), and rights — worth one sales inquiry each as leverage/backup.
4. Guardian Open Platform current commercial terms (possible free supplement; low priority).
5. Whether GDELT should later feed a coverage-triangulation signal (not evidence display) — deferred.
6. Whether snippets (if licensed later) measurably improve MNE classification vs. headline-only — testable post-MVP.

## 17. Recommended next implementation sprint

**Not the Historical News Backfill MVP** — it is Blocked / Deferred per §14. The next sprint should continue product work requiring no new data spend, drawing from: an AI Analyst layer using persisted MNE outputs only; personalization and alerts; product packaging and monetization; authentication and production hardening. When budget and written rights confirmation land, the deferred MVP specification in §14 is ready to hand off without re-research (re-verify pricing and terms at that time, as they may have changed).
