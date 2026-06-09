"""
Unit tests for probability_engine.py
Covers: prompt building, fallback assessment, response parsing.
Claude API is fully mocked — no real API calls made.
"""

import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.analysis.probability_engine import build_prompt, get_probability, _fallback_assessment


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def make_full_context(direction="short", aligned=3, probability=68):
    """Build a minimal but complete context dict for testing."""
    return {
        "direction":      direction,
        "trigger_tf":     "15m",
        "current_price":  20000.0,
        "timestamp":      "2026-06-02T10:30:00",
        "is_rth":         True,
        "trends": {
            "1h":  {"trend": "bear", "ema": 20050.0, "close": 20000.0},
            "30m": {"trend": "bear", "ema": 20040.0, "close": 20000.0},
            "15m": {"trend": "bear", "ema": 20030.0, "close": 20000.0},
            "5m":  {"trend": "bull", "ema": 19990.0, "close": 20000.0},
        },
        "alignment": {
            "aligned": aligned,
            "total":   4,
            "detail":  {"1h": True, "30m": True, "15m": True, "5m": False},
        },
        "sweep": {
            "direction":   direction,
            "level_type":  "session high",
            "level_price": 20100.0,
            "level_date":  "2026-05-30",
            "sweep_size":  5.0,
            "close_price": 20080.0,
        },
        "vwap":          19980.0,
        "poc_primary":   19970.0,
        "above_vwap":    True,
        "near_poc":      True,
        "near_vwap":     False,
        "vwap_dist":     20.0,
        "poc_dist":      30.0,
        "vol_stats":     {"ratio": 2.1, "spike": True, "avg": 1000, "current": 2100},
        "atr":           8.0,
        "atr_5m":        6.0,
        "atr_15m":       8.0,
        "atr_30m":       12.0,
        "atr_1h":        20.0,
        "session_levels": [
            {"date": "2026-05-30", "high": 20100.0, "low": 19900.0}
        ],
        "session_pocs":  [{"date": "2026-05-30", "poc": 19970.0}],
        "conditions": {
            "sweep_confirmed":  True,
            "reversal_candle":  True,
            "near_poc":         True,
            "vwap_confluence":  True,
            "1h_trend_aligned": True,
            "tf_3plus_aligned": True,
            "rth_session":      True,
        },
        "ext_conditions": {
            "near_spy_level": False,
            "near_spx_level": False,
            "near_pivot":     False,
        },
        "confluence_score":  8,
        "base_score":        8,
        "ext_score":         0,
        "total_conditions":  11,
        "levels_ctx":        None,
        "nearest_levels":    {},
        "tp_estimate":       12.0,
        "sl_estimate":       6.0,
        "rr_estimate":       2.0,
        "bars_available":    {"1h": 50, "30m": 100, "15m": 150, "5m": 300},
        "session_count":     3,
    }


def make_claude_response(payload: dict) -> MagicMock:
    """Build a mock requests.post response returning valid Claude JSON."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "content": [{"type": "text", "text": json.dumps(payload)}]
    }
    return mock_resp


# ─────────────────────────────────────────────
# _fallback_assessment
# ─────────────────────────────────────────────

class TestFallbackAssessment:

    def test_returns_dict(self):
        result = _fallback_assessment("test reason")
        assert isinstance(result, dict)

    def test_required_keys_present(self):
        result = _fallback_assessment("test")
        for key in ["probability", "confidence", "assessment", "reasoning",
                    "key_risk", "tp_adjust", "sl_adjust", "source"]:
            assert key in result

    def test_source_is_fallback(self):
        result = _fallback_assessment("test")
        assert result["source"] == "fallback"

    def test_assessment_is_watch(self):
        result = _fallback_assessment("test")
        assert result["assessment"] == "watch"

    def test_adjusts_default_to_one(self):
        result = _fallback_assessment("test")
        assert result["tp_adjust"] == 1.0
        assert result["sl_adjust"] == 1.0

    def test_reason_included_in_reasoning(self):
        result = _fallback_assessment("connection timeout")
        assert "connection timeout" in result["reasoning"]


# ─────────────────────────────────────────────
# build_prompt
# ─────────────────────────────────────────────

class TestBuildPrompt:

    def test_returns_string(self):
        ctx = make_full_context()
        prompt = build_prompt(ctx)
        assert isinstance(prompt, str)

    def test_contains_direction(self):
        ctx = make_full_context(direction="short")
        prompt = build_prompt(ctx)
        assert "SHORT" in prompt

    def test_contains_direction_long(self):
        ctx = make_full_context(direction="long")
        prompt = build_prompt(ctx)
        assert "LONG" in prompt

    def test_contains_all_timeframes(self):
        ctx = make_full_context()
        prompt = build_prompt(ctx)
        for tf_label in ["1-Hour", "30-Min", "15-Min", "5-Min"]:
            assert tf_label in prompt

    def test_contains_alignment_count(self):
        ctx = make_full_context(aligned=3)
        prompt = build_prompt(ctx)
        assert "3/4" in prompt

    def test_contains_vwap(self):
        ctx = make_full_context()
        prompt = build_prompt(ctx)
        assert "VWAP" in prompt

    def test_contains_sweep_level(self):
        ctx = make_full_context()
        prompt = build_prompt(ctx)
        assert "20100" in prompt

    def test_contains_confluence_score(self):
        ctx = make_full_context()
        prompt = build_prompt(ctx)
        assert "8" in prompt

    def test_ends_with_json_instruction(self):
        ctx = make_full_context()
        prompt = build_prompt(ctx)
        assert "JSON" in prompt


# ─────────────────────────────────────────────
# get_probability
# ─────────────────────────────────────────────

class TestGetProbability:

    VALID_RESPONSE = {
        "probability": 68,
        "confidence":  "high",
        "assessment":  "take",
        "reasoning":   "Strong 3/4 alignment with 1H bear trend confirmed.",
        "key_risk":    "VWAP reclaim could invalidate setup.",
        "tp_adjust":   1.1,
        "sl_adjust":   1.0,
    }

    @patch("src.analysis.probability_engine.requests.post")
    def test_returns_dict_with_required_keys(self, mock_post):
        mock_post.return_value = make_claude_response(self.VALID_RESPONSE)
        ctx = make_full_context()
        result = get_probability(ctx)
        for key in ["probability", "confidence", "assessment", "reasoning", "key_risk"]:
            assert key in result

    @patch("src.analysis.probability_engine.requests.post")
    def test_probability_value_correct(self, mock_post):
        mock_post.return_value = make_claude_response(self.VALID_RESPONSE)
        ctx = make_full_context()
        result = get_probability(ctx)
        assert result["probability"] == 68

    @patch("src.analysis.probability_engine.requests.post")
    def test_assessment_value_correct(self, mock_post):
        mock_post.return_value = make_claude_response(self.VALID_RESPONSE)
        ctx = make_full_context()
        result = get_probability(ctx)
        assert result["assessment"] == "take"

    @patch("src.analysis.probability_engine.requests.post")
    def test_source_is_claude_on_success(self, mock_post):
        mock_post.return_value = make_claude_response(self.VALID_RESPONSE)
        ctx = make_full_context()
        result = get_probability(ctx)
        assert result["source"] == "claude"

    @patch("src.analysis.probability_engine.requests.post")
    def test_fallback_on_api_error(self, mock_post):
        mock_post.side_effect = Exception("Connection refused")
        ctx = make_full_context()
        result = get_probability(ctx)
        assert result["source"] == "fallback"
        assert result["assessment"] == "watch"

    @patch("src.analysis.probability_engine.requests.post")
    def test_fallback_on_invalid_json(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": "not valid json {{{"}]
        }
        mock_post.return_value = mock_resp
        ctx = make_full_context()
        result = get_probability(ctx)
        assert result["source"] == "fallback"

    def test_empty_context_returns_fallback(self):
        result = get_probability({})
        assert result["source"] == "fallback"

    def test_none_context_returns_fallback(self):
        result = get_probability(None)
        assert result["source"] == "fallback"

    @patch("src.analysis.probability_engine.requests.post")
    def test_tp_sl_adjustments_passed_through(self, mock_post):
        response = {**self.VALID_RESPONSE, "tp_adjust": 1.2, "sl_adjust": 0.9}
        mock_post.return_value = make_claude_response(response)
        ctx = make_full_context()
        result = get_probability(ctx)
        assert result["tp_adjust"] == pytest.approx(1.2)
        assert result["sl_adjust"] == pytest.approx(0.9)
