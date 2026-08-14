import unittest
from pathlib import Path

from fastapi import Request

import dashboard
from mne.entitlements import EntitlementDenied


class DesignSystemStructureTests(unittest.TestCase):
    def test_dashboard_hierarchy_and_discovery_preview_are_ordered(self):
        source = Path("templates/dashboard.html").read_text(encoding="utf-8")
        ordered = ['id="overview"', '_partials/narrative_constellation.html', 'id="stories"', 'id="my-narratives"', 'id="markets"', 'id="events"', 'id="evidence"']
        positions = [source.index(marker) for marker in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('_partials/narrative_constellation.html', source)
        constellation = Path("templates/_partials/narrative_constellation.html").read_text(encoding="utf-8")
        self.assertIn("Explore in Research", Path("mne/presentation_language.py").read_text(encoding="utf-8"))
        self.assertIn("data-attention-cloud", constellation)

    def test_market_preview_uses_expression_roles_not_price_table(self):
        source = Path("templates/dashboard.html").read_text(encoding="utf-8")
        market = source[source.index('id="markets"'):source.index('id="events"')]
        for role in ("primary", "secondary", "offset"):
            self.assertIn(role, market)
        self.assertNotIn("latest_close", market)

    def test_xray_and_locked_components_use_native_and_shared_structures(self):
        xray = Path("templates/_partials/xray_disclosure.html").read_text(encoding="utf-8")
        locked = Path("templates/_partials/locked_state.html").read_text(encoding="utf-8")
        self.assertIn("<details", xray)
        self.assertIn("<summary", xray)
        self.assertIn("locked-state", locked)
        self.assertIn("View account and plan", locked)

    def test_entitlement_denial_renders_component(self):
        scope = {"type": "http", "method": "GET", "path": "/history", "headers": [], "query_string": b"", "server": ("test", 80), "client": ("test", 1), "scheme": "http", "app": dashboard.app, "router": dashboard.app.router}
        response = __import__("asyncio").run(dashboard.calm_entitlement_error(Request(scope), EntitlementDenied("upgrade_required")))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.template.name, "entitlement_denied.html")
        self.assertEqual(response.context["message"], "This feature is not included with your current plan.")

    def test_reserved_and_unsafe_language_do_not_leak_to_ui(self):
        sources = "\n".join(Path(path).read_text(encoding="utf-8") for path in ["templates/dashboard.html", "mne/presentation_language.py"])
        for term in ("Attention Velocity", "Primary-Source Support", "target price", "buy signal", "sell signal"):
            self.assertNotIn(term.lower(), sources.lower())
        self.assertNotIn("Narrative Gravity", sources)
        naming = Path("docs/ui_naming_framework.md").read_text(encoding="utf-8")
        self.assertIn("| Daily Launch Line |", naming)
        self.assertNotIn("**Daily Launch Line:** reserved", naming)

    def test_reduced_motion_and_two_hue_aliases_exist(self):
        css = Path("static/styles.css").read_text(encoding="utf-8")
        self.assertIn("prefers-reduced-motion: reduce", css)
        self.assertIn("--teal: var(--up)", css)
        self.assertIn("--amber: #f0a64b", css)

    def test_watchlist_uses_shared_shell_and_cloud_controls(self):
        dashboard_source = Path("templates/dashboard.html").read_text(encoding="utf-8")
        cloud_source = Path("templates/_partials/narrative_constellation.html").read_text(encoding="utf-8")
        css = Path("static/styles.css").read_text(encoding="utf-8")
        self.assertIn("dashboard-content-shell", dashboard_source)
        self.assertIn("data-watchlist-panel", dashboard_source)
        self.assertIn("data-cloud-star", cloud_source)
        self.assertIn("grid-template-columns: minmax(0, 1fr) 260px", css)
        self.assertIn("max-width: 1484px", css)

    def test_dashboard_uses_mockup_topbar_and_parity_sections(self):
        source = Path("templates/dashboard.html").read_text(encoding="utf-8")
        topbar = Path("templates/_partials/app_topbar.html").read_text(encoding="utf-8")
        self.assertNotIn('_partials/app_rail.html', source)
        self.assertIn('_partials/app_topbar.html', source)
        self.assertIn('class="dashboard-topbar"', topbar)
        for route in ('href="/"', 'href="/research"', 'href="/studio"', 'href="/preferences"', 'href="/login"'):
            self.assertIn(route, topbar)
        for route in ('href="/history"', 'href="/admin"'):
            self.assertNotIn(route, topbar)
        for component in ("parity-group-card", "parity-sector-tile", "parity-read-column"):
            self.assertIn(component, source)

    def test_sprint_j_pages_use_shared_topbar_without_filename_header(self):
        migrated = (
            "research_selector.html", "narrative_investigation.html",
            "sector_isolation.html", "asset_exploration.html",
            "asset_execution.html", "narrative_history.html",
            "preferences.html", "account.html",
            "historical_selector.html", "historical_request.html",
            "historical_request_status.html", "entitlement_denied.html",
            "historical_investigation.html",
        )
        for template in migrated:
            with self.subTest(template=template):
                source = Path("templates", template).read_text(encoding="utf-8")
                self.assertIn('_partials/app_topbar.html', source)
                self.assertNotIn('_partials/app_rail.html', source)
                self.assertNotIn("Latest meaningful run:", source)
                self.assertIn("app-topbar-page", source)

        for template in (
            "admin.html", "historical_workflow.html",
            "historical_research.html", "historical_comparison.html",
        ):
            source = Path("templates", template).read_text(encoding="utf-8")
            self.assertIn('_partials/app_rail.html', source)

    def test_preferences_and_account_use_v2_topbar_scope(self):
        for template in ("preferences.html", "account.html"):
            with self.subTest(template=template):
                source = Path("templates", template).read_text(encoding="utf-8")
                self.assertIn("app-topbar-page", source)
                self.assertIn("preferences-account-v2-page", source)
                self.assertNotIn("user-historical-page", source)

    def test_research_finder_is_progressive_and_uses_real_topic_controls(self):
        source = Path("templates/research_selector.html").read_text(encoding="utf-8")
        script = Path("static/research_finder.js").read_text(encoding="utf-8")
        css = Path("static/styles.css").read_text(encoding="utf-8")
        for marker in ("finderInput", "finderClear", "chipCrypto", "nrvList", "indexEmpty"):
            self.assertIn(marker, source)
        for theme in ("ai", "rates", "inflation", "energy", "recession"):
            self.assertIn(theme, source)
        self.assertIn("data-narrative-card", source)
        self.assertIn("data-story", source)
        self.assertIn("activeThemes", script)
        self.assertNotIn("fetch(", script)
        self.assertIn('nrv-card{% if narrative.scored %} direction-', source)
        self.assertIn('story-chip direction-{{ story.direction }}', source)
        self.assertIn(".research-finder-page .state-chip.direction-up", css)
        self.assertIn(".research-finder-page .nrv-card.direction-up", css)

    def test_studio_shell_has_saved_rail_placeholder_and_compare_panel(self):
        source = Path("templates/studio.html").read_text(encoding="utf-8")
        compare = Path("templates/_partials/studio_compare.html").read_text(encoding="utf-8")
        styles = Path("static/styles.css").read_text(encoding="utf-8")
        script = Path("static/artboard.js").read_text(encoding="utf-8")
        self.assertIn('_partials/app_topbar.html', source)
        for marker in ("studio-grid", "studio-rail", "studio-rail-row", "studio-tracked-mark", "studio-workbench"):
            self.assertIn(marker, source + styles)
        for marker in ("studio-compare-form", "studio-picker", "studio-compare-result"):
            self.assertIn(marker, compare + styles)
        self.assertIn('action="/studio/board/{{ board_id }}/compare"', compare)
        self.assertIn("data-studio-board", source)
        self.assertIn("artboard.js", source)
        self.assertIn("studio-evidence-{{ item.kind }}", source)
        self.assertIn("item.kind == 'headline'", source)
        self.assertIn("source_story:node.source_story", script)
        self.assertIn('label:"supports"', script)
        self.assertIn("data-add-evidence", script)
        for excluded in ("dropzone", "connectors", "draggable"):
            self.assertNotIn(excluded, source)
        self.assertIn("background: var(--teal)", styles)
        self.assertIn(".studio-compare-card", styles)

    def test_investigation_v2_has_real_jump_targets_and_sprint_m_modules(self):
        source = Path("templates/narrative_investigation.html").read_text(encoding="utf-8")
        styles = Path("static/styles.css").read_text(encoding="utf-8")
        for target in (
            "investigation-snapshot", "investigation-memory", "investigation-explanation",
            "investigation-clock", "investigation-market", "investigation-sectors",
            "investigation-stories", "supporting-evidence",
        ):
            self.assertIn(f'#{target}', source)
            self.assertIn(f'id="{target}"', source)
        for marker in ("strength-area", "spark-dot", "mini-candle", "cat-grid"):
            self.assertIn(marker, source)
        for marker in ("inv-story-grid", "sector-strip", "sector-tag-detached"):
            self.assertIn(marker, source + styles)
        self.assertIn(".sector-tag-detached .sector-stripe { background:var(--amber); }", styles)
        self.assertNotIn(".sector-tag-detached .sector-stripe { background:var(--red); }", styles)
        self.assertIn("prefers-reduced-motion:reduce", styles)


if __name__ == "__main__":
    unittest.main()
