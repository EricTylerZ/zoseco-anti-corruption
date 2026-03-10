"""Tests for momentum detection and cascade logic."""

import unittest
from unittest.mock import patch

from strategy.momentum import scan_momentum, detect_cascade, get_dynamic_allocation
from data.market_data import detect_momentum


class TestDetectMomentum(unittest.TestCase):
    """Test individual ticker momentum detection."""

    @patch("data.market_data.get_price_history")
    def test_bearish_momentum_aligned(self, mock_history):
        """Bearish thesis + price dropping = aligned momentum."""
        mock_history.return_value = [
            {"date": "2026-03-01", "close": 100.0},
            {"date": "2026-03-02", "close": 98.0},
            {"date": "2026-03-03", "close": 96.0},
            {"date": "2026-03-04", "close": 94.0},
            {"date": "2026-03-05", "close": 92.0},
        ]
        result = detect_momentum("TSN", direction="bearish")
        self.assertTrue(result["aligned"])
        self.assertLess(result["pct_change"], 0)
        self.assertIn(result["signal"], ("weak", "strong"))
        self.assertGreater(result["strength"], 0)

    @patch("data.market_data.get_price_history")
    def test_bullish_momentum_aligned(self, mock_history):
        """Bullish thesis + price rising = aligned momentum."""
        mock_history.return_value = [
            {"date": "2026-03-01", "close": 20.0},
            {"date": "2026-03-02", "close": 21.0},
            {"date": "2026-03-03", "close": 22.5},
            {"date": "2026-03-04", "close": 23.0},
            {"date": "2026-03-05", "close": 24.0},
        ]
        result = detect_momentum("SLV", direction="bullish")
        self.assertTrue(result["aligned"])
        self.assertGreater(result["pct_change"], 0)
        self.assertEqual(result["signal"], "strong")

    @patch("data.market_data.get_price_history")
    def test_no_momentum_flat(self, mock_history):
        """Flat price = no momentum signal."""
        mock_history.return_value = [
            {"date": "2026-03-01", "close": 50.0},
            {"date": "2026-03-02", "close": 50.1},
            {"date": "2026-03-03", "close": 49.9},
            {"date": "2026-03-04", "close": 50.0},
            {"date": "2026-03-05", "close": 50.2},
        ]
        result = detect_momentum("UUP", direction="bearish")
        self.assertEqual(result["signal"], "none")
        self.assertEqual(result["strength"], 0.0)

    @patch("data.market_data.get_price_history")
    def test_no_history_returns_none_signal(self, mock_history):
        """Missing data returns no signal."""
        mock_history.return_value = None
        result = detect_momentum("FAKE", direction="bearish")
        self.assertEqual(result["signal"], "none")
        self.assertFalse(result["aligned"])

    @patch("data.market_data.get_price_history")
    def test_against_thesis_negative_strength(self, mock_history):
        """Price moving against thesis direction = negative strength."""
        mock_history.return_value = [
            {"date": "2026-03-01", "close": 50.0},
            {"date": "2026-03-02", "close": 52.0},
            {"date": "2026-03-03", "close": 54.0},
            {"date": "2026-03-04", "close": 56.0},
            {"date": "2026-03-05", "close": 58.0},
        ]
        result = detect_momentum("UUP", direction="bearish")
        self.assertFalse(result["aligned"])
        self.assertLess(result["strength"], 0)


class TestCascadeDetection(unittest.TestCase):
    """Test cascade (system-wide collapse) detection."""

    def test_no_momentum_conservative(self):
        """No momentum across theses = conservative mode."""
        momentum = {
            "beef_imports": {"thesis_signal": "none", "thesis_strength": 0.0},
            "dollar_collapse": {"thesis_signal": "none", "thesis_strength": 0.0},
            "nyc_housing": {"thesis_signal": "none", "thesis_strength": 0.0},
        }
        result = detect_cascade(momentum)
        self.assertFalse(result["cascade"])
        self.assertEqual(result["recommended_mode"], "conservative")

    def test_single_thesis_active(self):
        """One thesis moving = aggressive mode."""
        momentum = {
            "beef_imports": {"thesis_signal": "none", "thesis_strength": 0.0},
            "dollar_collapse": {"thesis_signal": "strong", "thesis_strength": 0.8},
            "nyc_housing": {"thesis_signal": "none", "thesis_strength": 0.0},
        }
        result = detect_cascade(momentum)
        self.assertFalse(result["cascade"])
        self.assertEqual(result["recommended_mode"], "aggressive")
        self.assertEqual(result["active_theses"], ["dollar_collapse"])

    def test_all_theses_cascade(self):
        """All theses moving = cascade mode."""
        momentum = {
            "beef_imports": {"thesis_signal": "weak", "thesis_strength": 0.3},
            "dollar_collapse": {"thesis_signal": "strong", "thesis_strength": 0.8},
            "nyc_housing": {"thesis_signal": "weak", "thesis_strength": 0.4},
        }
        result = detect_cascade(momentum)
        self.assertTrue(result["cascade"])
        self.assertEqual(result["recommended_mode"], "maximum")

    def test_two_strong_cascade(self):
        """Two strong signals = cascade."""
        momentum = {
            "beef_imports": {"thesis_signal": "strong", "thesis_strength": 0.9},
            "dollar_collapse": {"thesis_signal": "strong", "thesis_strength": 0.7},
            "nyc_housing": {"thesis_signal": "none", "thesis_strength": 0.0},
        }
        result = detect_cascade(momentum)
        self.assertTrue(result["cascade"])
        self.assertEqual(result["recommended_mode"], "maximum")


class TestDynamicAllocation(unittest.TestCase):
    """Test dynamic allocation shifts based on momentum."""

    def test_conservative_keeps_base(self):
        """No momentum = base allocation unchanged."""
        momentum = {
            "beef_imports": {"thesis_signal": "none", "thesis_strength": 0.0},
            "dollar_collapse": {"thesis_signal": "none", "thesis_strength": 0.0},
            "nyc_housing": {"thesis_signal": "none", "thesis_strength": 0.0},
        }
        cascade = {"recommended_mode": "conservative", "active_theses": []}
        alloc = get_dynamic_allocation(momentum, cascade)
        self.assertAlmostEqual(alloc["beef_imports"], 0.25, places=2)
        self.assertAlmostEqual(alloc["dollar_collapse"], 0.45, places=2)
        self.assertAlmostEqual(alloc["nyc_housing"], 0.30, places=2)

    def test_aggressive_shifts_to_hot(self):
        """Active thesis gets more allocation, inactive gets less."""
        momentum = {
            "beef_imports": {"thesis_signal": "none", "thesis_strength": 0.0},
            "dollar_collapse": {"thesis_signal": "strong", "thesis_strength": 0.8},
            "nyc_housing": {"thesis_signal": "none", "thesis_strength": 0.0},
        }
        cascade = {
            "recommended_mode": "aggressive",
            "active_theses": ["dollar_collapse"],
        }
        alloc = get_dynamic_allocation(momentum, cascade)

        # Dollar collapse should get more than base 45%
        self.assertGreater(alloc["dollar_collapse"], 0.45)
        # Others should get less
        self.assertLess(alloc["beef_imports"], 0.25)
        self.assertLess(alloc["nyc_housing"], 0.30)
        # Should still sum to 1.0
        self.assertAlmostEqual(sum(alloc.values()), 1.0, places=2)

    def test_maximum_concentrates_heavily(self):
        """Cascade mode steals 70% from inactive."""
        momentum = {
            "beef_imports": {"thesis_signal": "none", "thesis_strength": 0.0},
            "dollar_collapse": {"thesis_signal": "strong", "thesis_strength": 0.9},
            "nyc_housing": {"thesis_signal": "strong", "thesis_strength": 0.6},
        }
        cascade = {
            "recommended_mode": "maximum",
            "active_theses": ["dollar_collapse", "nyc_housing"],
        }
        alloc = get_dynamic_allocation(momentum, cascade)

        # Beef should be heavily reduced (70% stolen)
        self.assertLess(alloc["beef_imports"], 0.10)
        # Active theses should be boosted
        self.assertGreater(alloc["dollar_collapse"], 0.45)
        self.assertAlmostEqual(sum(alloc.values()), 1.0, places=2)


if __name__ == "__main__":
    unittest.main()
