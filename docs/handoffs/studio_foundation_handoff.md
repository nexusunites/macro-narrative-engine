# Studio Foundation - Implementation Handoff

**Status: not implemented - ready to hand to Codex. Do not implement from this document in this
session, and do not stage, commit, or push.** This is a Codex-ready brief for the FOUNDATION portion
of the Studio arc, delivered as three strictly serial sprints (N -> O -> P). It adds a story-centric
Saved store, the Studio shell + contextual rail, and a Compare-over-time tool; it changes no scoring,
no thresholds, and no taxonomy. Every claim below was re-verified against the codebase; the file:line
references are current as of 2026-08-11.

---

## 1. Purpose and canonical references

Studio is the hands-on workspace from the approved mockup - a contextual left rail (Watchlist +
Saved), an artboard canvas, and a Compare-over-time tool tagged "Was: History". This handoff covers
three sequential, independently shippable, browser-audited sprints:

- **Sprint N** - the **Saved-stories backend**: a new per-user store keyed by story slug, its
  validation + repository diffing, the write route, the entitlement + capacity plumbing, wiring the
  currently-disabled Research story stars, and a Preferences section.
- **Sprint O** - the **Studio shell + contextual rail + nav**: add Studio to the top bar, a `/studio`
  route + template with the Watchlist/Saved rail driven by Sprint N's store, and a tasteful "coming
  next" placeholder where the artboard canvas will later live.
- **Sprint P** - the **Compare tool inside Studio**: a Compare-over-time panel that reuses the
  existing user historical-comparison builder, re-applying the same entitlement + usage gate the
  standalone `/history/compare` route uses.

**The ARTBOARD CANVAS is explicitly OUT OF SCOPE here.** It gets its own mockup-first design round
later (**Sprint Q**, flagged in section 9). Sprint O ships only a tasteful placeholder in the canvas
area. Do not build drag/drop, node connectors, or any artboard interaction in this arc.

**Canonical references (in precedence order):**

1. **Visual contract:** `docs/mockups/research_studio_concept_v1.html` - a self-contained,
   pure-ASCII HTML+CSS+JS mockup checked in beside this handoff. It carries a slim top bar and three
   views; **only the Studio view (`#view-studio`, L1128-1220) and its nav item (L733) are in scope
   here** (the Research finder/investigation views were the prior arc). Open it in a browser while
   building. **Where this document and the mockup disagree on pixels, the mockup wins; where they
   disagree on scope or data honesty, this document wins.**
2. **Written visual contract:** `docs/design_system.md` (Design System v2) - the token set, card
   system, semantic color rules, and component patterns bind this work.
3. **Charter:** `AGENTS.md` - standing rules, especially never stage/commit/push, terminology
   discipline (all user-facing copy via `mne/presentation_language.py`), fail-closed persistence, and
   honest empty states.

**Accurate description of the mockup's Studio view (read it before starting).**

- **Nav item** (`.nav-link[data-nav="studio"]`, mockup L733): a "Studio" item sits between Research
  and Preferences in the primary nav.
- **Studio view** (`#view-studio`, L1128-1220): a two-column `.studio-grid`.
  - **Contextual left rail** (`.rail`, L1132-1150): two stacked rail cards. The first is
    **Watchlist** (`#watchList`, L1133-1140) with the note "The stories you're actively tracking - a
    subset of Saved below." The second is **Saved** (`#savedList`, L1142-1149) with the note
    "Everything you starred in Research." Each rail row (`railRow`, L1553-1578) renders a drag grip, a
    **direction glyph** (`GLYPH[s.dir]` -> up/down/steady), the story name, and - only in the Saved
    list when the story is also tracked - a small "Tracked" mark (`.tracked-mark`, L1571-1575). The
    rail render (L1580-1591) shows every WATCH story in Watchlist and every SAVED story in Saved,
    marking the subset overlap.
  - **Main area** (`.studio-main`, L1152-1217): an eyebrow row with a "Concept - next build" tag
    (L1155-1158), a headline + subtitle, then the **artboard** (`.artboard`, L1163-1192, OUT OF
    SCOPE - placeholder only), then a **Compare tool card** (L1194-1216): an eyebrow "Compare tool"
    with a "Was: History" tag, the heading "Compare over time", a one-line description, and two
    pickers **Point A** / **Point B** (L1202-1214) each showing a date and a narrative state line,
    separated by a "vs".

The mockup's Saved/Watchlist seed data (`SAVED`, `WATCH`, `STORIES`, L1346-1352) and the Compare
pickers are **illustrative literals**. The production build replaces them with the real Saved store
(Sprint N) and the real replay list + comparison builder (Sprint P), but must preserve the rendered
anatomy of the in-scope surfaces.

---

## 2. Ratified decisions (owner-confirmed 2026-08-11; state prominently, do not re-litigate)

These are pre-ratified by the owner. Do not re-open them; flag only genuinely new ambiguity
(AGENTS.md).

- **Story-centric Saved.** Studio's "Saved" is a collection of starred **STORIES** (story slugs from
  `config/story_registry.json`). "Watchlist" is a **TRACKED SUBSET** of Saved (each saved story
  carries a `tracked` flag; Watchlist = the saved stories with `tracked` true). This is a **NEW
  store**, separate from the existing followed-narrative (group/theme) store, which stays exactly
  as-is. The dashboard "watchlist" remains narrative-follow and is **NOT reworked here**. (A future
  unification of narrative-follow + saved-stories is noted in section 9; do **not** build it.)
- **Foundation first, artboard deferred.** N (Saved backend) -> O (Studio shell + rail) -> P (Compare
  tool), strictly serial. The artboard canvas is its own later mockup-first design round (Sprint Q);
  Sprint O ships a placeholder only, with a clean seam.
- **Studio joins the nav.** Add "Studio" to the top bar. It was deliberately omitted in the prior arc
  (the shared partial `templates/_partials/app_topbar.html` currently lists Overview / Research /
  Preferences only, L6-10) - this handoff adds the real Studio item now that it is being built.
- **No story-slug store existed before this arc.** The followed-narrative store cannot key by story
  slug (section 3). The prior arc shipped the Research story stars as inert "coming with Studio"
  affordances (verified: copy "Story saving is coming with Studio",
  `mne/presentation_language.py:270-271, 323`; disabled buttons at `research_selector.html:112` and
  `narrative_investigation.html:347`). Sprint N is what makes them real.

---

## 3. Data reality and honesty rules (read before writing any code)

- **The followed-narrative store cannot hold a story slug.** `FollowedNarrative(id, user_id,
  narrative_level String(16), narrative_key String(120))` with
  `UniqueConstraint(user_id, narrative_level, narrative_key)` at `mne/models.py:67-73`, and
  `narrative_level` is limited to `_NARRATIVE_LEVELS = ("theme", "group")`
  (`mne/personalization.py:31`). A story slug is neither a theme nor a group, so it **cannot** be
  stored under this model. Sprint N adds a **separate** `SavedStory` model; it does **not** overload
  or migrate the followed-narrative store.
- **Slugs are validated against the registry, fail-closed.** Valid slugs are exactly the keys of
  `load_story_registry()` (`mne/story_registry.py:136`), each matching `_SLUG =
  re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")` (`mne/story_registry.py:18`). Any slug not present in the
  registry is rejected. Validation must fail closed (return `None`) on any malformed input, exactly
  like its siblings `validate_preferences` (`mne/personalization.py:59-105`) and
  `_validate_saved_view` do.
- **Honest empty states everywhere.** A user who has saved nothing sees an honest empty state ("Star
  stories in Research to build your collection"), never a blank rail. An anonymous visitor sees a
  sign-in prompt, never a fake save. Compare shows an honest state before selection and when no
  replays exist. No fabricated stories, no fabricated comparisons.
- **No engine-language leak, no run filenames.** All user-facing copy routes through
  `mne/presentation_language.py` (AGENTS.md). Raw engine terms and raw run filenames never render.
- **Color budget (Design System v2).** Direction glyphs use **teal = strengthening (up), amber =
  fading (down), slate = steady**. **Red is downside price only and is never used for story state or
  participation** anywhere in these surfaces. Reuse the finder's existing `direction-{{direction}}`
  state classes (e.g. `research_selector.html:110`); do not introduce a new color mapping.

---

## 4. Sprint N - Saved-stories backend + wire the Research stars

**Goal:** add a per-user, story-slug-keyed Saved store with a `tracked` flag, validate it fail-closed
against the registry, diff it through the account repository, expose a write route mirroring the
followed-narrative route, wire the Research story stars to it for authenticated users, and add a
Preferences section. Backend + wiring only; the Studio page is Sprint O.

### 4.1 New model `SavedStory` (mirror `FollowedNarrative`)

- Add to `mne/models.py` **beside** `FollowedNarrative` (`mne/models.py:67-73`), copying its idiom:

  ```
  class SavedStory(Base):
      __tablename__ = "saved_stories"
      id: Mapped[int] = mapped_column(Integer, primary_key=True)
      user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), index=True)
      story_slug: Mapped[str] = mapped_column(String(120), nullable=False)
      tracked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
      __table_args__ = (UniqueConstraint("user_id", "story_slug"),)
  ```

  `Integer`, `String`, `Boolean`, `ForeignKey`, `UniqueConstraint`, `Mapped`, `mapped_column` are
  already imported in `models.py` (used by `FollowedNarrative`). Use `String(120)` to match the
  slug-length ceiling the sibling `_safe_key` enforces.
- **Alembic migration** in `/alembic/versions/`. The current head is `0002_entitlements_usage`
  (`revision = "0002_entitlements_usage"`, `down_revision = "0001_accounts"`). Add a new revision
  (e.g. `0003_saved_stories`) with `down_revision = "0002_entitlements_usage"`. `upgrade()` creates
  the `saved_stories` table (id PK, user_id FK to `users.user_id` with `ondelete="CASCADE"` + index,
  story_slug String(120) not null, tracked Boolean not null default False, unique
  `(user_id, story_slug)`); `downgrade()` drops it. Match the column types and the FK/index/unique
  shape used by `0001_accounts` for `followed_narratives`.

### 4.2 Extend `mne/personalization.py` (pure functions, fail-closed)

- `build_default_preferences` (`mne/personalization.py:44-56`) gains a `"saved_stories": []` key
  (add it beside `"followed_narratives": []`, L50). Each element is `{"story_slug": <slug>,
  "tracked": <bool>}`.
- `validate_preferences` (`mne/personalization.py:59-105`) gains a `saved_stories` block modeled on
  the `followed_narratives` block (L68-81):
  - `value.get("saved_stories")` must be a `list`, else return `None`.
  - For each item: must be a `dict`; `story_slug` must be a valid registry slug (present in the set of
    `load_story_registry().stories` slugs - iterate the loaded registry's stories for their `.slug`);
    `tracked` must be a `bool`. On any deviation return `None`.
  - Dedupe by `story_slug` (keep the first occurrence, like the `if record not in normalized_followed`
    guard at L79). Assign the normalized list to `result["saved_stories"]`.
  - **Import discipline:** import `load_story_registry` from `mne.story_registry` inside the function
    or at module top; if the registry fails to load, fail closed (treat as no valid slugs -> reject
    any non-empty saved list, or return `None`). State which you chose.
- Add pure helpers mirroring `follow_narrative` / `unfollow_narrative` (`mne/personalization.py:131-147`),
  e.g. `save_story(profile, story_slug)`, `unsave_story(profile, story_slug)`, and
  `set_story_tracked(profile, story_slug, tracked)`. `save_story` validates the slug (raise
  `ValueError` on an unknown slug, mirroring the `follow_narrative` guard) and appends
  `{"story_slug", "tracked": False}` if absent; `unsave_story` removes the row; `set_story_tracked`
  flips `tracked` on an existing saved row (a no-op if the slug is not saved - do not implicitly
  create it, or state your choice). Keep them `deepcopy`-based and side-effect-free like their
  siblings.

### 4.3 Extend `mne/account_repository.py` (assemble + diff)

- `load_preferences` (`mne/account_repository.py:56-70`): add `saved_stories` to the assembled
  profile, mirroring the `followed` query (L62) and the `followed_narratives` mapping (L68). Query
  `SavedStory` rows for the user ordered by id, and set
  `saved_stories=[{"story_slug": x.story_slug, "tracked": bool(x.tracked)} for x in saved]`. Import
  `SavedStory` from `mne.models` (add to the existing import at L10).
- `save_preferences` (`mne/account_repository.py:73-91`): after validation, diff `SavedStory` rows
  keyed on `(user_id, story_slug)`, mirroring the `FollowedNarrative` diff (L80-84):
  - build `existing = {x.story_slug: x for x in db.scalars(select(SavedStory).where(...))}`,
  - `wanted = {x["story_slug"]: x for x in normalized["saved_stories"]}`,
  - **delete** rows whose slug is not wanted,
  - **add** rows for wanted slugs not present,
  - **update** the `tracked` flag on rows whose slug persists but whose `tracked` changed (this is the
    one difference from the followed-narrative diff, which has no mutable field - do not forget the
    update pass).

### 4.4 Entitlement + capacity plumbing

- **Entitlement:** add a new `SAVED_STORIES` feature to `mne/entitlements.py`, mirroring
  `FOLLOWED_NARRATIVES` (declared at `mne/entitlements.py:18`, listed in `FEATURES` L26-32, included
  in `_FREE_FEATURES` L34-38). Add `SAVED_STORIES = "SAVED_STORIES"`, append it to `FEATURES`, and add
  it to `_FREE_FEATURES` (a free feature for all plans, like followed narratives). No matrix change
  beyond adding it to the free set (PRO/TEAM inherit via `_PRO_FEATURES = _FREE_FEATURES | {...}`).
- **Capacity metric:** add a `SAVED_STORIES` capacity metric to `mne/usage_limits.py`, mirroring
  `FOLLOWED_NARRATIVES` (declared L16, in `CAPACITY_METRICS` L20, per-plan caps L27/34/41 wired into
  `_LIMITS` L46-65). Add the constant, add it to `CAPACITY_METRICS`, define
  `FREE_SAVED_STORIES` / `PRO_SAVED_STORIES` / `TEAM_SAVED_STORIES` caps, and wire them into all three
  plan dicts in `_LIMITS`. **The cap numbers are an owner decision (section 9)** - pick placeholder
  values that mirror the followed-narrative caps (FREE 3 / PRO 25 / TEAM 100 at
  `usage_limits.py:27,34,41`) and flag them for the owner rather than inventing final numbers.
- **Capacity counting:** `require_capacity` -> `can_consume_usage` -> `get_usage_consumed` routes
  CAPACITY_METRICS to `usage_repository.capacity_count(user_id, metric)`
  (`mne/usage_limits.py:98-99`). `capacity_count` (`mne/usage_repository.py:77-87`) currently branches
  on `FOLLOWED_NARRATIVES` / `SAVED_HISTORICAL_VIEWS` / `ALERT_RULES`. **Add a `SAVED_STORIES`
  branch** that counts `SavedStory` rows for the user
  (`db.scalar(select(func.count()).select_from(SavedStory).where(SavedStory.user_id == user_id))`),
  mirroring the `FollowedNarrative` branch (L80-81); import `SavedStory` alongside the existing model
  imports and add `SAVED_STORIES` to that function's local `from mne.usage_limits import ...` (L78).
  **Without this branch, capacity always reads 0 and every save is denied - do not skip it.**
- **Whether Watchlist (tracked) needs its own capacity** vs. just being a flag on a saved story is an
  **owner decision (section 9)**. Default for this sprint: `tracked` is a plain flag with **no
  separate capacity metric**; only the Saved collection is capacity-gated. Do not add a second metric
  unless the owner asks.

### 4.5 New write route `POST /preferences/stories`

Mirror `change_followed_narrative` (`dashboard.py:2771-2795`) almost line-for-line:

- `require_authenticated_user(request)`, then `form = _form(await request.body()); _csrf(request,
  form)` (the CSRF helper is `dashboard.py:218-219`).
- Read `story_slug`, `action` in `{save, unsave, track, untrack}`, and `return_to`.
- **Whitelist `return_to`** to `{"/preferences", "/research", "/studio"}` (the followed route
  whitelists `{"/preferences", "/research"}` at `dashboard.py:2779-2780`; add `/studio`), defaulting
  to `/preferences` otherwise.
- `profile = account_repository.load_preferences(user.user_id)`, then inside `try:`:
  - on `action == "save"` for a slug not already saved: `require_entitlement(user, SAVED_STORIES)` +
    `require_capacity(user, SAVED_STORIES)` **before** mutating (mirror the guard ordering at
    `dashboard.py:2784-2786`), then `profile = save_story(profile, story_slug)`.
  - `unsave` -> `unsave_story(profile, story_slug)`.
  - `track` / `untrack` -> `set_story_tracked(profile, story_slug, action == "track")`.
  - `account_repository.save_preferences(user.user_id, profile)`.
  - Swallow `ValueError` (`except ValueError: pass`, as at L2793-2794) so a bad slug or over-capacity
    save fails quietly.
- Return `RedirectResponse(return_to, status_code=303)`.
- **Import** the new entitlement/metric: add `SAVED_STORIES as SAVED_STORIES_FEATURE` to the
  `mne.entitlements` import (`dashboard.py:131`) and `SAVED_STORIES` to the `mne.usage_limits` import
  (`dashboard.py:132-134`), following the existing `FOLLOWED_NARRATIVES as FOLLOWED_NARRATIVES_FEATURE`
  aliasing (feature vs. capacity metric share the string name in two modules; alias one to avoid the
  clash, exactly as the followed-narrative code already does).
- Note that `EntitlementDenied` raised outside the `try` (it is a `PermissionError`, not a
  `ValueError`, so it is **not** swallowed) surfaces through the existing app handler
  `calm_entitlement_error` (`dashboard.py:199-211`) -> `entitlement_denied.html` (403). The
  followed-narrative route raises entitlement/capacity errors **inside** its `try` and thus swallows
  them to a silent redirect; **match that behavior** (raise inside the `try` so an over-capacity save
  is a quiet no-op redirect, not a 403), unless the owner prefers the 403 surface - flag if unsure.

### 4.6 Wire the Research story stars (authenticated users)

The stars exist but are inert. Two surfaces:

- **Finder chips** (`templates/research_selector.html:109-113`): the `span.story-chip` carries
  `data-search` and `data-theme` but **not the slug**; the star button (`button.sc-star`, L112) is
  `aria-disabled="true"`. The story data already carries `slug` (`mne/research_workspace.py:182-190`),
  so the template can render it. Add `data-slug="{{ story.slug }}"` to the chip (or a hidden input),
  and for **authenticated users** replace the disabled star with a live control that POSTs to
  `/preferences/stories` with `story_slug` + `action=save|unsave` + `return_to=/research`. Reflect
  saved state (filled star vs. hollow) and add a **tracked** toggle (`action=track|untrack`). The
  handler at `static/research_finder.js:80-84` currently only sets a "coming with Studio" hint on
  click - replace that for authed users with either a real form submit or a small `fetch` mirroring
  `static/personalization.js` (the history-save fetch at `personalization.js:4-27` builds a
  `URLSearchParams` body and POSTs). **If you use a `fetch`, you MUST include `csrf_token` in the
  body** - the route calls `_csrf`, and `validate_csrf` (`mne/security.py:57-60`) rejects a missing
  token with 403. (Note: the existing `personalization.js` history fetch omits the token; do **not**
  replicate that omission here.) The JS-disabled path must still work via a real `<form>` POST with a
  hidden `csrf_token` (mirror the Preferences narratives form, `templates/preferences.html:20-24`).
- **Investigation cards** (`templates/narrative_investigation.html:340-355`): the story loop has
  `story.slug` available (`mne/research_workspace.py:346-356`); the star button (L347) is `disabled`.
  Apply the same treatment: for authed users, a live save/unsave control (and tracked toggle) POSTing
  to `/preferences/stories` with `return_to=/research` (or the investigation URL - keep it in the
  whitelist by using `/research`).
- **Anonymous users keep a sign-in prompt.** Gate the live control on `{% if current_user %}`
  (mirroring the dashboard narrative-watchlist gating); anonymous users see a sign-in affordance and
  the honest "coming with Studio" copy is replaced only for authed users. Do not fake a save for
  signed-out visitors.
- **Copy:** the existing "coming with Studio" strings (`research_finder_copy().story_star`
  `presentation_language.py:270`; `research_investigation_copy` `story_star` L323) should be joined by
  new keys for the live states ("Save"/"Saved"/"Track"/"Tracked"/"Sign in to save"). Add them to
  `RESEARCH_FINDER_COPY` (`presentation_language.py:241-278`) and the investigation copy dict; never
  inline strings in the template or JS.

### 4.7 Preferences page - 4th section "Saved stories"

Add a 4th `<section class="content-section">` to `templates/preferences.html` (it currently has
three: Follow narratives L16, Alerts L29, Saved historical views L38). Iterate
`personalization.preferences.saved_stories` and, joining each slug to the registry for its
`display_name`, render a row per saved story with a form POSTing to `/preferences/stories` (same
pattern as the narratives section, `preferences.html:16-27`): a hidden `csrf_token`, a hidden
`story_slug`, an unsave button (`action=unsave`), and a track/untrack toggle
(`action=track|untrack`). Honest empty state when the collection is empty. The route/context that
renders Preferences (`preferences_page`, `dashboard.py:2752-2768`) already passes `personalization`
(from `build_personalization_context`), which after 4.3 carries `saved_stories`; pass the story
registry (or a slug -> display_name map) into the context so the template can name each slug.

### 4.8 Files to touch (Sprint N)

- `mne/models.py` - **new** `SavedStory` model beside `FollowedNarrative`.
- `alembic/versions/` - **new** migration (down_revision `0002_entitlements_usage`).
- `mne/personalization.py` - `build_default_preferences` + `validate_preferences` + new pure helpers.
- `mne/account_repository.py` - assemble + diff `SavedStory` in `load_preferences` / `save_preferences`.
- `mne/entitlements.py` - new `SAVED_STORIES` feature (free).
- `mne/usage_limits.py` - new `SAVED_STORIES` capacity metric + per-plan caps.
- `mne/usage_repository.py` - `SAVED_STORIES` branch in `capacity_count`.
- `dashboard.py` - new `POST /preferences/stories` route + imports; pass a slug->name map into the
  Preferences context.
- `templates/research_selector.html`, `static/research_finder.js`,
  `templates/narrative_investigation.html` - wire the stars (authed) / sign-in prompt (anon).
- `templates/preferences.html` - the 4th "Saved stories" section.
- `mne/presentation_language.py` - new copy keys.

### 4.9 Test plan (Sprint N)

- **Model + migration:** `SavedStory` maps the expected columns and unique constraint; the migration
  applies (`upgrade`) and reverts (`downgrade`) cleanly against a scratch database.
- **`validate_preferences` saved-stories cases:** a valid registry slug is kept; an unknown slug is
  rejected (returns `None`); duplicate slugs dedupe; a non-bool `tracked` is rejected; a non-list
  `saved_stories` is rejected; malformed input fails closed (mirror the sibling followed-narrative
  tests).
- **Repository round-trip:** save a profile with saved stories, reload, and confirm the rows + the
  `tracked` flag persist; changing `tracked` updates the row (not delete+add); unsaving deletes.
- **Route:** unauthenticated -> auth required; missing/invalid CSRF -> 403; over-capacity save denied
  (verify `capacity_count` reflects the new metric); `save` / `unsave` / `track` / `untrack` each
  mutate the store and redirect 303 to a whitelisted `return_to`; a non-whitelisted `return_to`
  falls back to `/preferences`; a bad slug is a quiet no-op.
- **Wiring:** the finder chip and investigation card carry the slug for authed users and post to
  `/preferences/stories`; anonymous users get the sign-in prompt and no live control.

Run: `./venv/bin/python -m unittest discover tests`. Two pre-existing `test_authorization` failures
are known and unrelated; nothing in Sprint N should add a failure.

---

## 5. Sprint O - Studio shell + rail + nav

**Depends on Sprint N's store.** Add Studio to the nav, a `/studio` route + template rendering the
contextual Watchlist/Saved rail from the Saved store, and a tasteful placeholder in the artboard
area. No Compare tool yet (that is Sprint P); no artboard interaction (deferred to Sprint Q).

### 5.1 Add Studio to the shared top bar

- `mne/presentation_language.py`: add `"nav_studio": "Studio"` to `DASHBOARD_PARITY_COPY`
  (`presentation_language.py:199-207`, beside `nav_research`).
- `dashboard.py`: add `"nav_studio"` to `TOPBAR_COPY_KEYS` (`dashboard.py:155-158`) so the
  `dashboard_copy` Jinja global (built at `dashboard.py:166-168`) carries it. (Optionally also add it
  to `DASHBOARD_PARITY_COPY_KEYS` at `dashboard.py:1272-1280`; the top bar renders from the
  `dashboard_copy` global, so `TOPBAR_COPY_KEYS` is the load-bearing one.)
- `templates/_partials/app_topbar.html`: add a "Studio" nav item **between Research and Preferences**
  (currently L8-9), matching the mockup order Overview / Research / Studio / Preferences (mockup
  L729-735). Follow the existing pattern exactly: `<a{% if active_tier == "studio" %} class="active"
  aria-current="page"{% endif %} href="/studio">{{ dashboard_copy.nav_studio }}</a>` with the same
  middot separator span the other items use. Do not hardcode the label.

### 5.2 Route + context builder

- Add `GET /studio -> studio_page(request)` in `dashboard.py`. **Owner-deferred decision (section 9):
  auth-only vs. signed-out teaser.** Default for this sprint: render for everyone but drive the rail
  from the user's Saved store when signed in, and show a **sign-in prompt** in the rail for anonymous
  visitors (mirror how the finder stars gate on `current_user`). Do **not** hard-gate with
  `require_authenticated_user` unless the owner chooses auth-only - flag it.
- Assemble the rail data from `account_repository.load_preferences(user.user_id)["saved_stories"]`
  (available after Sprint N) for a signed-in user, joining each slug to the registry via
  `load_story_registry()` for its `display_name`, and deriving a direction glyph. **Reuse the
  finder's existing direction data:** the finder already produces per-story
  `{slug, display_name, direction, direction_label}` in `build_narrative_selector`
  (`mne/research_workspace.py:181-190`); the cleanest path is to build a `slug -> {display_name,
  direction, direction_label}` map from that same selector output for the latest meaningful run and
  look each saved slug up in it. Stories not present in today's read still render by name with a
  steady/neutral glyph (honest - the store persists the star regardless of today's scoring). Build two
  lists: `saved` (all saved stories) and `watchlist` (the subset with `tracked` true), and mark the
  overlap so the template can show the "Tracked" mark on saved rows that are also tracked (mockup
  `renderRail`, L1580-1591).
- Set `active_tier = "studio"` in the context and pass `dashboard_copy` (via
  `DASHBOARD_PARITY_COPY_KEYS`, as the research route does at `dashboard.py:2723-2724`) plus
  `current_user` (already a context-processor global, `dashboard.py:160-163`) so the shared top bar
  renders.
- **No engine leak:** do not pass raw run dicts or filenames into the Studio context - only the
  presentation-shaped rail rows.

### 5.3 Template `templates/studio.html`

- **New** template using `{% include "_partials/app_topbar.html" %}` and the Design System v2 card
  system, matching the mockup's Studio view (`#view-studio`, L1128-1220):
  - a two-column layout (rail + main), collapsing to one column on narrow widths (no horizontal
    scroll at 390);
  - the **contextual left rail** with a **Watchlist** card (saved stories where `tracked` is true,
    with the "actively tracking - a subset of Saved" note) and a **Saved** card (all saved stories),
    each row showing the direction glyph (teal up / amber down / slate steady, reusing the finder's
    `direction-{{direction}}` classes) + the story `display_name`, and a small **"Tracked"** mark on
    Saved rows that are also tracked (mockup L1571-1575). Do **not** render the drag grip as an
    interactive affordance (dragging is Sprint Q) - a static grip glyph or its omission is fine.
  - an **honest empty state** when the user has saved nothing: "Star stories in Research to build your
    collection" (route the copy through `presentation_language.py`);
  - a **sign-in prompt** for anonymous visitors instead of the rail lists.
  - the **main area**: eyebrow + headline + subtitle, then the **artboard PLACEHOLDER** - a tasteful
    "coming next" concept card carrying a "Concept - next build" tag (mockup L1155-1160), **not** the
    interactive artboard. Leave a clear seam/comment (e.g. `{# Sprint Q: artboard canvas #}`) so the
    later sprint drops in cleanly. Do not build drop zones, connectors, or nodes.
- All copy via `presentation_language.py` (add a `STUDIO_COPY` dict + accessor mirroring
  `research_finder_copy`, `presentation_language.py:279-281`): headline, subtitle, rail labels
  ("Watchlist", "Saved", the two notes, "Tracked"), the empty state, the sign-in prompt, and the
  placeholder card copy.

### 5.4 Files to touch (Sprint O)

- `mne/presentation_language.py` - `nav_studio` copy + a `STUDIO_COPY` dict/accessor.
- `dashboard.py` - `nav_studio` in `TOPBAR_COPY_KEYS`; new `/studio` route + rail context builder.
- `templates/_partials/app_topbar.html` - the Studio nav item.
- `templates/studio.html` - **new** template.
- `static/styles.css` - Studio shell + rail styles (port `.studio-grid` / `.rail` / `.rail-card` /
  `.rail-row` / `.tracked-mark` / the placeholder card recipes from the mockup, L303-347, L1132-1160).

### 5.5 Verification (Sprint O)

- `/studio` returns **200** for both an authenticated user (with and without saved stories) and an
  anonymous visitor.
- The rail renders the Saved list and the Watchlist (tracked subset), with the "Tracked" mark on the
  overlap; the honest empty state renders for a user with nothing saved; the sign-in prompt renders
  for anonymous.
- The top bar shows Overview / Research / **Studio** / Preferences with Studio **active** on `/studio`
  (and the other pages still highlight correctly).
- No engine-language leak, no run filename in the rendered page.
- Widths 1280 / 1024 / 390: no horizontal scroll; JS-disabled: the page and rail render server-side;
  reduced-motion honored; color budget (teal/amber/slate; red never for state).

---

## 6. Sprint P - Compare tool in Studio

**Depends on Sprint O's page.** Add a "Compare over time" panel to `templates/studio.html` that reuses
the existing user historical-comparison **builder** (not the standalone template), re-applying the same
entitlement + usage gate the standalone route uses. Keep `/history/compare` working.

### 6.1 Reuse the builder, not the template

- The engine is `build_user_historical_comparison(replay_a, replay_b)`
  (`mne/historical_comparison_view.py:20`), which loads two replay artifacts, auto-orders them
  chronologically, and compares theme/group scores. The route-level context assembler is
  `build_user_historical_comparison_context(request, replay_a, replay_b)` (`dashboard.py:2578-...`),
  which returns `{replays, comparison, invalid, copy, replay_a, replay_b}` and returns early (with
  `comparison=None`) when neither picker is set (`dashboard.py:2597-2598`). **Reuse this builder
  as-is.**
- Replay pickers come from `list_user_replays()` (`mne/historical_research_view.py:28-53`), each card
  exposing `url_id`, `date`, `dominant_group`, `dominant_theme` (mockup Point A / Point B pickers,
  L1202-1214). The builder already puts `replays` in its context.
- The existing template `templates/historical_comparison_user.html` is a **full standalone page** (its
  own top bar + form), rendered by `user_historical_comparison` (`dashboard.py:3104-3122`). Studio
  needs a **panel**, not a page - build a new partial (e.g.
  `templates/_partials/studio_compare.html`) that reuses the builder's `comparison` / `replays` /
  `copy` data. Do not restyle or repurpose the standalone page.

### 6.2 Wire it into Studio

- **Recommended shape (owner-deferrable, section 9): a `/studio/compare` sub-route** that renders the
  Studio page with the compare panel populated, taking `replay_a` / `replay_b` query params (mirror
  the `/history/compare` signature at `dashboard.py:3104-3109`, which reads them via
  `Query(default="")`). Alternatively, fold the params into the main `/studio` GET. Pick one and flag
  the choice; the sub-route keeps `/studio` cheap when Compare is unused.
- In the Studio route (or sub-route), when **both** pickers are set, call
  `build_user_historical_comparison_context(request, replay_a, replay_b)` and merge its
  `comparison` / `replays` / `copy` / `invalid` into the Studio context. When neither is set, still
  pass `replays` (so the pickers render) with `comparison=None`.
- **Re-apply the gate exactly as the standalone route does** (`dashboard.py:3111-3115`): only when a
  `comparison` was produced and a user is present, call `require_entitlement(user,
  HISTORICAL_COMPARISON)` + `consume_usage(user, HISTORICAL_COMPARISONS, object_reference="|".join(
  sorted((replay_a, replay_b))))`. `HISTORICAL_COMPARISON` is a **free** feature for all plans
  (`mne/entitlements.py:37`) but fails closed for non-ACTIVE accounts; `HISTORICAL_COMPARISONS` is a
  monthly consumption metric (FREE cap 1, `mne/usage_limits.py:24,48`). **The builder does NOT gate -
  the route must.** Do not skip the `consume_usage` call, or the free monthly allowance is bypassed.
- `EntitlementDenied` (raised by either guard) is not caught here; it surfaces through the existing
  app handler `calm_entitlement_error` (`dashboard.py:199-211`) -> `entitlement_denied.html` (403),
  exactly as `/history/compare` relies on.

### 6.3 The panel template

- Render the mockup's Compare card (L1194-1216): the "Compare tool" eyebrow with the **"Was:
  History"** tag, the "Compare over time" heading, the one-line description, and the two pickers
  (Point A / Point B, populated from `replays`, each showing date + dominant group/theme + a direction
  glyph) with a "vs" between them. Below the pickers, render the comparison result inline when
  `comparison` is present (reuse the whitelisted fields the builder already exposes; do not invent new
  ones).
- **Honest empty states:** before any selection, an honest "Pick two points in time to compare"
  prompt; when `list_user_replays()` returns nothing, an honest "No saved reconstructions to compare
  yet" state; when `invalid` is set (one picker only, or a bad id), the builder's existing invalid
  copy. Never fabricate a comparison.
- All copy via the builder's `HISTORICAL_COPY` (already in context as `copy`) and any new keys through
  `presentation_language.py`. JS-disabled: the pickers are a plain `<form method="get">` submitting to
  the Studio compare route (no JS required); reduced-motion honored.

### 6.4 Keep `/history/compare` working

Do **not** remove or alter `user_historical_comparison` (`dashboard.py:3104-3122`) or
`templates/historical_comparison_user.html`. The Studio panel is additive; the standalone route
remains reachable and must still return 200.

### 6.5 Files to touch (Sprint P)

- `dashboard.py` - `/studio/compare` sub-route (or extend `/studio`); wire the builder + re-apply the
  entitlement/usage gate.
- `templates/studio.html` - include the compare panel.
- `templates/_partials/studio_compare.html` - **new** panel partial (reuses the builder data).
- `mne/presentation_language.py` - new copy keys only if the panel needs a phrase that does not exist.
- `static/styles.css` - `.compare-body` / `.compare-pickers` / `.picker` recipes ported from the
  mockup (L405-...).

### 6.6 Verification (Sprint P)

- Studio Compare renders with two valid replay ids and shows the inline comparison; the entitlement +
  usage gate is enforced (a non-ACTIVE or over-allowance account surfaces `entitlement_denied.html`
  403; a free account's first comparison consumes one of its monthly allowance).
- Honest states: no selection -> prompt; one picker only / bad id -> invalid copy; no replays ->
  no-replays state. No fabricated comparisons.
- `/history/compare` still returns 200 and renders the standalone page unchanged.
- `/studio` still returns 200; the top bar still highlights Studio.
- Widths 1280 / 1024 / 390: no horizontal scroll; JS-disabled: the picker form submits; reduced-motion
  honored; color budget respected (teal/amber/slate; red never for state).

---

## 7. Sprint ordering and gating

**N -> O -> P, strictly serial.** O's rail needs N's store; P adds the Compare panel to O's page. Each
sprint is **independently shippable** and is **audited in-browser before any commit** (committing is
Daniel's step, never the agent's). Do not start O before N is verified, or P before O. Do not fold two
sprints into one change set. **Sprint Q (the artboard canvas) is a deferred, mockup-first design round
and is OUT OF SCOPE here** - Sprint O ships only the placeholder and a clean seam.

---

## 8. Verification standard (applies to every sprint)

The repo standard:

- Full test suite via **`./venv/bin/python -m unittest discover tests`** (pytest is **not** installed
  in this venv - use unittest). Two pre-existing `test_authorization` failures are known and
  unrelated; do not "fix" them and do not let them mask new failures.
- Dashboard up: `./venv/bin/python -m uvicorn dashboard:app --port 8643`. These routes return
  **200**: `/`, `/research`, `/preferences`, and the new `/studio` (Sprint O onward). Auth-gated
  writes (`POST /preferences/stories`) require authentication + a valid CSRF token.
- The new migration applies cleanly (`upgrade`) and reverts (`downgrade`) against a scratch database.
- Rendering checked against the latest real run and honest empty/degraded states (nothing saved;
  anonymous visitor; no replays).
- **UI checks (Sprints O, P):** widths **1280 / 1024 / 390** with no horizontal scroll; **JS-disabled**
  rendering; **reduced-motion** honored; **color budget** against `docs/design_system.md` (teal /
  amber / slate; **red is downside price only and never encodes story state or participation**); **no
  run filename in the UI**; **no engine-language leak** in primary copy.
- `git diff --check` clean; **nothing staged, committed, or pushed.** Runtime data (the account
  database, replays) lives outside the repo; never write runtime outputs into the repository.

---

## 9. Open decisions for the owner (flag, do not decide silently)

1. **SAVED_STORIES capacity caps.** The per-plan numbers (FREE / PRO / TEAM) are placeholders
   mirroring the followed-narrative caps (3 / 25 / 100). Confirm the real caps.
2. **Watchlist (tracked) capacity.** Default: `tracked` is a plain flag with no separate capacity
   metric (only the Saved collection is capacity-gated). Should Watchlist have its own cap?
3. **/studio auth model.** Default: render for everyone with a sign-in prompt in the rail for
   anonymous visitors. Alternative: auth-only (`require_authenticated_user`). Flag if you prefer
   auth-only.
4. **Compare placement.** Default recommendation: a `/studio/compare` sub-route. Alternative: fold the
   compare params into the main `/studio` GET. Confirm.
5. **Story-save write behavior on denial.** Default (mirroring the followed-narrative route): raise
   entitlement/capacity errors inside the `try` so an over-capacity save is a quiet no-op redirect.
   Alternative: let it surface `entitlement_denied.html` (403). Confirm.
6. **Future unification.** Whether to eventually unify the narrative-follow store and the
   saved-stories store into one personalization surface. Noted only; do not build.
7. **Artboard canvas (Sprint Q).** The interactive artboard is a deferred, mockup-first design round.
   Sprint O ships a placeholder. Out of scope here.

---

## Appendix - quick reference (all re-verified 2026-08-11)

| Claim | Location | What is there |
|---|---|---|
| Followed-narrative model (cannot key by slug) | `mne/models.py:67-73` | `FollowedNarrative`; `UniqueConstraint(user_id, narrative_level, narrative_key)` |
| `AccountPreferences` / `SavedHistoricalView` (model siblings) | `mne/models.py:58-84` | column idioms to mirror for `SavedStory` |
| Narrative levels limit | `mne/personalization.py:31` | `_NARRATIVE_LEVELS = ("theme", "group")` |
| Default preferences | `mne/personalization.py:44-56` | add `saved_stories: []` beside `followed_narratives` |
| `validate_preferences` (fail-closed pattern) | `mne/personalization.py:59-105` | followed-narrative block L68-81 to mirror |
| Pure follow/unfollow helpers | `mne/personalization.py:131-147` | `follow_narrative` / `unfollow_narrative` idiom |
| Repo assemble | `mne/account_repository.py:56-70` | `load_preferences`; followed mapping L68 |
| Repo diff | `mne/account_repository.py:73-91` | `save_preferences`; followed diff L80-84 (add `tracked` update) |
| Story registry loader + slug regex | `mne/story_registry.py:136, 18` | `load_story_registry`; `_SLUG` |
| Entitlements: FOLLOWED_NARRATIVES + free set | `mne/entitlements.py:18, 26-38` | mirror for new `SAVED_STORIES` free feature |
| `EntitlementDenied` / `require_entitlement` | `mne/entitlements.py:44-48, 65-68` | fail-closed |
| Usage: FOLLOWED_NARRATIVES capacity + caps | `mne/usage_limits.py:16, 20, 27/34/41, 46-65` | mirror for `SAVED_STORIES` metric |
| `require_capacity` / `consume_usage` | `mne/usage_limits.py:113-126` | capacity + consumption gates |
| `capacity_count` branches | `mne/usage_repository.py:77-87` | add `SAVED_STORIES` -> count `SavedStory` rows |
| Followed write route (mirror) | `dashboard.py:2771-2795` | auth, `_csrf`, action, whitelisted `return_to`, entitlement+capacity, swallow ValueError, 303 |
| CSRF helper + validator | `dashboard.py:218-219`; `mne/security.py:57-60` | `_csrf`; `validate_csrf` rejects missing token 403 |
| Entitlement app handler | `dashboard.py:199-211` | `calm_entitlement_error` -> `entitlement_denied.html` 403 |
| Dashboard entitlement/usage imports (aliasing) | `dashboard.py:131-134` | `FOLLOWED_NARRATIVES as FOLLOWED_NARRATIVES_FEATURE` etc. |
| Finder story chip (no slug yet) + disabled star | `templates/research_selector.html:109-113` | `data-search`/`data-theme`; `sc-star` `aria-disabled` |
| Finder star handler (hint only) | `static/research_finder.js:80-84` | sets "coming with Studio" hint |
| Investigation story card + disabled star | `templates/narrative_investigation.html:340-355, 347` | `story.slug` available; star `disabled` |
| Finder story shape (carries slug) | `mne/research_workspace.py:181-190` | `{slug, display_name, direction, direction_label, ...}` |
| Investigation story shape (carries slug) | `mne/research_workspace.py:346-356` | `{slug, display_name, direction, direction_label, matched_count, example}` |
| "coming with Studio" copy | `mne/presentation_language.py:270-271, 323` | `story_star` / `studio_hint` |
| Personalization JS fetch pattern | `static/personalization.js:4-27` | URLSearchParams POST (omits csrf - do not copy that omission) |
| Preferences page route + sections | `dashboard.py:2752-2768`; `templates/preferences.html:16, 29, 38` | narratives/alerts/history; add 4th section |
| Preferences narratives form (mirror) | `templates/preferences.html:16-27` | hidden csrf + form POST |
| Shared top bar (add Studio) | `templates/_partials/app_topbar.html:6-10` | Overview/Research/Preferences nav |
| Top-bar copy keys + global | `dashboard.py:155-158, 166-168` | `TOPBAR_COPY_KEYS`; `dashboard_copy` global |
| Nav copy dict | `mne/presentation_language.py:199-207` | `DASHBOARD_PARITY_COPY` (add `nav_studio`) |
| Finder copy dict + accessor | `mne/presentation_language.py:241-278, 279-281` | `RESEARCH_FINDER_COPY` / `research_finder_copy()` |
| Compare context builder (reuse) | `dashboard.py:2578-...` | `build_user_historical_comparison_context` -> `{replays, comparison, invalid, copy}` |
| Compare engine | `mne/historical_comparison_view.py:20` | `build_user_historical_comparison`; auto-orders chronologically |
| Replay picker source | `mne/historical_research_view.py:28-53` | `list_user_replays` -> `url_id/date/dominant_group/dominant_theme` |
| Standalone compare route (keep working) | `dashboard.py:3104-3122` | `/history/compare`; gate at L3114-3115 |
| Compare entitlement + metric | `mne/entitlements.py:37`; `mne/usage_limits.py:24, 48` | HISTORICAL_COMPARISON free; HISTORICAL_COMPARISONS FREE cap 1 |
| Standalone compare template (do not reuse as panel) | `templates/historical_comparison_user.html` | full standalone page |
| Alembic head | `alembic/versions/0002_entitlements_usage.py:6-7` | `revision`/`down_revision` chain |
| Mockup Studio view | `docs/mockups/research_studio_concept_v1.html:1128-1220` | rail (Watchlist/Saved) + placeholder + Compare card |
| Mockup Studio nav item | `docs/mockups/research_studio_concept_v1.html:733` | `data-nav="studio"` between Research and Preferences |
| Mockup rail row + Tracked mark | `docs/mockups/research_studio_concept_v1.html:1553-1591` | glyph + name + subset "Tracked" mark |
| Mockup Compare card | `docs/mockups/research_studio_concept_v1.html:1194-1216` | "Was: History"; Point A / Point B pickers |
</content>
</invoke>
