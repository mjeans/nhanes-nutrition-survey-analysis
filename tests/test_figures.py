import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PublishedFigureTests(unittest.TestCase):
    def test_accessible_and_finite_svg_figures(self):
        for name in ["fiber-density-by-age.svg","sodium-density-by-age.svg","adjusted-associations.svg"]:
            content = (ROOT / "assets" / name).read_text(encoding="utf-8")
            svg = ET.fromstring(content)
            self.assertEqual(svg.attrib["role"], "img")
            for element in ("title", "desc"):
                self.assertTrue(svg.find("{http://www.w3.org/2000/svg}" + element).text)
            self.assertNotIn("nan", content.lower())
            self.assertNotIn("inf,", content.lower())
