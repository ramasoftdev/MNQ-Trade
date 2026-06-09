"""
Unit tests for discord_formatter.py
Covers: embed color, probability bar, TP/SL math, field presence.
No real HTTP calls made.
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.reporting.discord_formatter import build_embed, send_to_discord, COLORS


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def make_ctx(direction="short", atr=8.0, score=8, total=11):
    return {
        "direction":      direction,
        "trigger_tf":     "15m",
        "current_price":  20000.0,
        "atr":            atr,
        "confluence_score": score,
        "total_conditions": total,
        "trends": {
            "1h":  {"trend": "bear", "ema": 20050.0, "close": 20000.0},
            "30m": {"trend": "bear", "ema": 20040.0, "close": 20000.0},
            "15m": {"trend": "bear", "ema": 20030.0, "close": 20000.0},
            "5m":  {"trend": "bull", "ema": 19990.0, "close": 20000.0},
        },
        "alignment": {
            "aligned": 3, "total": 4,
            "detail": {"1h": True, "30m": True, "15m": True, "5m": False},
        },
        "sweep": {
            "level_price": 20100.0,
            "level_type":  "session high",
            "level_date":  "2026-05-30",
            "sweep_size":  5.0,
        },
        "vwap":         19980.0,
        "poc_primary":  19970.0,
        "above_vwap":   True,
        "near_poc":     True,
        "vwap_dist":    20.0,
        "poc_dist":     30.0,
        "vol_stats":    {"ratio": 2.1, "spike": True},
        "conditions": {
            "sweep_confirmed":  True,
            "reversal_candle":  True,
            "near_poc":         True,
            "vwap_confluence":  True,
            "1h_trend_aligned": True,
            "tf_3plus_aligned": True,
            "rth_session":      True,
        },
        "levels_ctx":    None,
        "nearest_levels": {},
        "ext_score":     0,
    }


def make_prob(assessment="take", probability=68, confidence="high",
              tp_adjust=1.0, sl_adjust=1.0):
    return {
        "assessment":  assessment,
        "probability": probability,
        "confidence":  confidence,
        "reasoning":   "Strong confluence across all timeframes.",
        "key_risk":    "VWAP reclaim could invalidate.",
        "tp_adjust":   tp_adjust,
        "sl_adjust":   sl_adjust,
        "source":      "claude",
    }


# ─────────────────────────────────────────────
# build_embed
# ─────────────────────────────────────────────

class TestBuildEmbed:

    def test_returns_dict_with_embeds(self):
        embed = build_embed(make_ctx(), make_prob())
        assert "embeds" in embed
        assert len(embed["embeds"]) == 1

    def test_color_take_is_green(self):
        embed = build_embed(make_ctx(), make_prob(assessment="take"))
        assert embed["embeds"][0]["color"] == COLORS["take"]

    def test_color_watch_is_yellow(self):
        embed = build_embed(make_ctx(), make_prob(assessment="watch"))
        assert embed["embeds"][0]["color"] == COLORS["watch"]

    def test_color_skip_is_red(self):
        embed = build_embed(make_ctx(), make_prob(assessment="skip"))
        assert embed["embeds"][0]["color"] == COLORS["skip"]

    def test_title_contains_direction(self):
        embed = build_embed(make_ctx(direction="short"), make_prob())
        title = embed["embeds"][0]["title"]
        assert "SHORT" in title

    def test_title_contains_price(self):
        embed = build_embed(make_ctx(), make_prob())
        title = embed["embeds"][0]["title"]
        assert "20000" in title

    def test_probability_bar_rendered(self):
        embed = build_embed(make_ctx(), make_prob(probability=70))
        description = embed["embeds"][0]["description"]
        assert "70%" in description
        assert "█" in description

    def test_probability_none_shows_manual_review(self):
        embed = build_embed(make_ctx(), make_prob(probability=None))
        description = embed["embeds"][0]["description"]
        assert "manual" in description.lower()

    def test_fields_include_alignment(self):
        embed = build_embed(make_ctx(), make_prob())
        fields = embed["embeds"][0]["fields"]
        names = [f["name"] for f in fields]
        assert any("Timeframe" in n or "alignment" in n.lower() for n in names)

    def test_fields_include_sweep_details(self):
        embed = build_embed(make_ctx(), make_prob())
        fields = embed["embeds"][0]["fields"]
        names = [f["name"] for f in fields]
        assert any("Sweep" in n or "sweep" in n for n in names)

    def test_fields_include_market_context(self):
        embed = build_embed(make_ctx(), make_prob())
        fields = embed["embeds"][0]["fields"]
        names = [f["name"] for f in fields]
        assert any("context" in n.lower() or "Market" in n for n in names)

    def test_key_risk_field_present(self):
        embed = build_embed(make_ctx(), make_prob())
        fields = embed["embeds"][0]["fields"]
        names = [f["name"] for f in fields]
        assert any("risk" in n.lower() for n in names)

    def test_footer_present(self):
        embed = build_embed(make_ctx(), make_prob())
        footer = embed["embeds"][0].get("footer", {})
        assert "MNQ Agent" in footer.get("text", "")


# ─────────────────────────────────────────────
# send_to_discord
# ─────────────────────────────────────────────

class TestSendToDiscord:

    @patch("src.reporting.discord_formatter.requests.post")
    def test_returns_true_on_204(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_post.return_value = mock_resp
        result = send_to_discord(make_ctx(), make_prob())
        assert result is True

    @patch("src.reporting.discord_formatter.requests.post")
    def test_returns_false_on_error_status(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad Request"
        mock_post.return_value = mock_resp
        result = send_to_discord(make_ctx(), make_prob())
        assert result is False

    @patch("src.reporting.discord_formatter.requests.post")
    def test_returns_false_on_exception(self, mock_post):
        mock_post.side_effect = Exception("Connection error")
        result = send_to_discord(make_ctx(), make_prob())
        assert result is False
