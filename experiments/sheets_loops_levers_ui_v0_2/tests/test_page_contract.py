import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PageContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.css = (ROOT / "essay.css").read_text(encoding="utf-8")
        cls.js = (ROOT / "essay.js").read_text(encoding="utf-8")

    def test_semantic_chapters_and_controls(self):
        self.assertEqual(self.html.count('role="tabpanel"'), 4)
        self.assertEqual(self.html.count('role="tab"'), 4)
        self.assertEqual(self.html.count('role="tablist"'), 1)
        for control in ("motif-select", "depth-range", "phase-range", "returned-toggle", "agent-toggle"):
            self.assertIn(f'id="{control}"', self.html)

    def test_responsive_accessible_svg_contract(self):
        self.assertGreaterEqual(self.html.count("viewBox="), 6)
        self.assertIn("prefers-reduced-motion", self.css)
        self.assertIn("@media (max-width: 600px)", self.css)
        self.assertIn("color-scheme: light dark", self.css)
        self.assertIn("role=\"img\"", self.html)

    def test_keyboard_and_claim_boundaries_are_visible(self):
        self.assertIn('event.key === "ArrowRight"', self.js)
        self.assertIn('"1": "sheets"', self.js)
        self.assertIn("not yet claimed", self.html)
        self.assertIn("singular-value uncertainty", self.html)
        self.assertIn("not camera motion", self.html)


if __name__ == "__main__":
    unittest.main()
