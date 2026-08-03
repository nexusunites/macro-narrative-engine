import unittest
from pathlib import Path

from fastapi import Request

import dashboard
from mne.entitlements import EntitlementDenied


class DesignSystemStructureTests(unittest.TestCase):
    def test_dashboard_hierarchy_and_discovery_preview_are_ordered(self):
        source = Path("templates/dashboard.html").read_text(encoding="utf-8")
        ordered = ['id="overview"', 'id="stories"', '_partials/narrative_constellation.html', 'id="my-narratives"', 'id="markets"', 'id="events"', 'id="evidence"']
        positions = [source.index(marker) for marker in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('_partials/narrative_constellation.html', source)
        constellation = Path("templates/_partials/narrative_constellation.html").read_text(encoding="utf-8")
        self.assertIn("Explore in Research", Path("mne/presentation_language.py").read_text(encoding="utf-8"))
        self.assertIn("data-constellation", constellation)

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
        for term in ("Attention Velocity", "Primary-Source Support", "Daily Launch Line", "target price", "buy signal", "sell signal"):
            self.assertNotIn(term.lower(), sources.lower())
        self.assertNotIn("Narrative Gravity", sources)

    def test_reduced_motion_and_two_hue_aliases_exist(self):
        css = Path("static/styles.css").read_text(encoding="utf-8")
        self.assertIn("prefers-reduced-motion: reduce", css)
        self.assertIn("--teal: var(--up)", css)
        self.assertIn("--amber: var(--down)", css)


if __name__ == "__main__":
    unittest.main()
