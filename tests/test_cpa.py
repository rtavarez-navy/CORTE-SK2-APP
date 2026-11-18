import unittest
from unittest.mock import patch

from web import cpa
from web.app import cpa_panel


class CpaTest(unittest.TestCase):
    def test_parse_order_and_set(self):
        for value in ("3986055 A", "SO-3986055 a", "3986055   A"):
            self.assertEqual(cpa.split_query(value), ("3986055", "A"))
        self.assertEqual(cpa.split_query("3986055"), ("3986055", None))
        with self.assertRaises(ValueError):
            cpa.split_query("3986055A")

    def test_exact_order_set_and_factory_with_reordered_columns(self):
        headers = ["Qty ⇅", "SO # ⇅", "Factory ⇅", "Set ⇅", "Line Status ⇅"]
        rows = [
            ["18", "SO-3986055", "JuiceSakira2", "A", "0900"],
            ["4", "SO-3986055", "JuiceSakira2", "AA", "0910"],
            ["99", "SO-3986055", "JuiceSakira2JTS3", "A", "1700"],
            ["3", "SO-39860550", "JuiceSakira2", "A", "1700"],
        ]
        self.assertEqual(cpa.select_lines(headers, rows, "3986055", "A"),
                         [cpa.Line("SO-3986055", "A", "18", "0900")])
        self.assertEqual(len(cpa.select_lines(headers, rows, "3986055", None)), 2)

    def test_panel_keeps_order_set_in_separate_cells(self):
        with patch("web.cpa.lookup", return_value=[cpa.Line("SO-3986055", "A", "18", "0900")]) as lookup:
            html = cpa_panel("", "3986055 A")
        lookup.assert_called_once_with("3986055 A")
        self.assertIn("<td>SO-3986055</td><td>A</td><td>18</td><td>0900</td>", html)
