"""
Component 5 — Discord Formatter (MTF Edition)
===============================================
Builds rich Discord embeds with a multi-timeframe alignment
section at the top so the key picture is visible at a glance.
"""

import logging
import requests
from datetime import datetime
import pytz
from src.data.config import DISCORD_WEBHOOK_URL, TIMEZONE

log = logging.getLogger("discord_formatter")
TZ  = pytz.timezone(TIMEZONE)

COLORS = {
    "take":    0x2ECC71,
    "watch":   0xF0B429,
    "skip":    0xE74C3C,
    "unknown": 0x888888,
}

DIRECTION_LABEL = {"long": "LONG ▲", "short": "SHORT ▼", "unknown": "SIGNAL"}

ASSESSMENT_LABEL = {
    "take":  "HIGH CONFLUENCE — Consider entry",
    "watch": "MODERATE — Wait for confirmation",
    "skip":  "LOW CONFLUENCE — Skip this setup",
}

CONFIDENCE_LABEL = {
    "high":   "High confidence",
    "medium": "Medium confidence",
    "low":    "Low confidence",
}

TF_LABEL = {"1h": "1H", "30m": "30m", "15m": "15m", "5m": "5m"}
TREND_ICON = {"bull": "▲", "bear": "▼", "unknown": "?"}


def _build_tf_alignment_field(ctx: dict) -> dict:
    """
    Builds the timeframe alignment summary field.
    Example:
      1H  ▼ BEAR  [✓]   30m ▼ BEAR  [✓]
      15m ▼ BEAR  [✓]   5m  ▲ BULL  [✗]
    """
    trends    = ctx.get("trends", {})
    alignment = ctx.get("alignment", {})
    detail    = alignment.get("detail", {})
    direction = ctx.get("direction", "unknown")

    lines = []
    row   = []
    for tf in ["1h", "30m", "15m", "5m"]:
        info    = trends.get(tf, {})
        trend   = info.get("trend", "unknown")
        icon    = TREND_ICON.get(trend, "?")
        aligned = detail.get(tf, False)
        check   = "✓" if aligned else "✗"
        row.append(f"`{TF_LABEL[tf]}` {icon} {trend.upper():<5} [{check}]")
        if len(row) == 2:
            lines.append("  ".join(row))
            row = []
    if row:
        lines.append(row[0])

    aligned_count = alignment.get("aligned", 0)
    total_count   = alignment.get("total", 4)
    summary       = f"**{aligned_count}/{total_count} timeframes aligned** with {direction.upper()}"

    return {
        "name":   f"Timeframe Alignment",
        "value":  summary + "\n" + "\n".join(lines),
        "inline": False,
    }


def _condition_line(name: str, passed: bool) -> str:
    icon  = "✓" if passed else "✗"
    label = name.replace("_", " ").title()
    return f"`{icon}` {label}"


def _build_spy_section(ctx: dict) -> dict:
    """
    Build SPY confluence check section for Discord.
    Shows SPY pivot, price, alignment, and contribution to score.
    """
    spy_price = ctx.get("spy_price", 0)
    direction = ctx.get("direction", "unknown").upper()
    spy_analysis = ctx.get("spy_analysis", {})
    ext_score = ctx.get("ext_score", 0)

    if not spy_analysis:
        return None

    pivot = spy_analysis.get("pivot", 0)
    pivot_direction = spy_analysis.get("pivot_direction", "unknown").upper()
    analysis_text = spy_analysis.get("analysis", "")

    # Determine alignment
    if direction == "LONG":
        aligned = pivot_direction == "UP"
    else:  # SHORT
        aligned = pivot_direction == "DOWN"

    alignment_icon = "✓" if aligned else "✗"
    alignment_text = "ALIGNED" if aligned else "DIVERGENT"

    # Determine position relative to pivot
    if spy_price > pivot:
        position = "ABOVE pivot (bullish bias)"
    elif spy_price < pivot:
        position = "BELOW pivot (bearish bias)"
    else:
        position = "AT pivot (neutral)"

    value = (
        f"**SPY Price:** {spy_price:.2f}\n"
        f"**Pivot:** {pivot:.2f} ({position})\n"
        f"**Direction Alignment:** `{alignment_icon}` {direction} {alignment_text}\n"
        f"**Magnet:** {analysis_text}\n"
        f"**Score Contribution:** +{ext_score} pts"
    )

    return {
        "name": "SPY Confluence Check",
        "value": value,
        "inline": False,
    }


def build_embed(ctx: dict, prob: dict) -> dict:
    direction  = ctx.get("direction", "unknown")
    price      = ctx.get("current_price", 0)
    sweep      = ctx.get("sweep") or {}
    conds      = ctx.get("conditions", {})
    score      = ctx.get("confluence_score", 0)
    total      = ctx.get("total_conditions", 10)
    trigger_tf = ctx.get("trigger_tf", "?").upper()
    assessment = prob.get("assessment", "unknown")
    probability= prob.get("probability")
    reasoning  = prob.get("reasoning", "")
    key_risk   = prob.get("key_risk", "")
    confidence = prob.get("confidence", "low")

    ts_str = datetime.now(TZ).strftime("%H:%M CT")

    # Probability display
    if probability is not None:
        bar_filled   = round(probability / 10)
        prob_display = f"[{'█' * bar_filled}{'░' * (10 - bar_filled)}] {probability}%"
    else:
        prob_display = "Manual review required"

    dir_label = DIRECTION_LABEL.get(direction, "SIGNAL")
    title     = f"MNQ {dir_label} — Liquidity Sweep @ {price:.2f}  ({trigger_tf})"

    description = (
        f"**{ASSESSMENT_LABEL.get(assessment, 'Review setup')}**\n"
        f"{prob_display}  |  {CONFIDENCE_LABEL.get(confidence, '')}\n\n"
        f"{reasoning}"
    )

    fields = [
        # 1. MTF alignment at the top
        _build_tf_alignment_field(ctx),

        # 2. Sweep details
        {
            "name": "Sweep details",
            "value": (
                f"Level: **{sweep.get('level_price', 'N/A')}**"
                f"  ({sweep.get('level_type','N/A')} — {sweep.get('level_date','N/A')})\n"
                f"Sweep size: **{sweep.get('sweep_size', 'N/A')} pts** beyond level"
            ),
            "inline": False,
        },

        # 3. Market context
        {
            "name": "Market context",
            "value": (
                f"VWAP: **{ctx.get('vwap',0):.2f}**"
                f"  (price {'above' if ctx.get('above_vwap') else 'below'}, {ctx.get('vwap_dist',0):.1f}pts)\n"
                f"POC:  **{ctx.get('poc_primary',0):.2f}**"
                f"  ({'near' if ctx.get('near_poc') else 'far'}, {ctx.get('poc_dist',0):.1f}pts)\n"
                f"Volume: **{ctx.get('vol_stats',{}).get('ratio',0):.1f}x avg**"
            ),
            "inline": False,
        },
    ]

    # 4. SPY Confluence Check (NEW - dedicated section)
    spy_section = _build_spy_section(ctx)
    if spy_section:
        fields.append(spy_section)

    # 5. Conditions
    fields.append({
        "name": f"Conditions ({score}/{total})",
        "value": "\n".join(_condition_line(k, v) for k, v in conds.items()),
        "inline": True,
    })

    if key_risk:
        fields.append({
            "name":   "Key risk",
            "value":  key_risk,
            "inline": False,
        })

    # 6. Target & Risk (TP/SL/R:R) - appears after key risk
    tp_estimate = ctx.get("tp_estimate", 0)
    sl_estimate = ctx.get("sl_estimate", 0)
    rr_estimate = ctx.get("rr_estimate", 0)
    tp_adjust = prob.get("tp_adjust", 1.0)
    sl_adjust = prob.get("sl_adjust", 1.0)

    if tp_estimate and sl_estimate:
        fields.append({
            "name": "Target & Risk",
            "value": (
                f"Entry: **{price:.2f}**\n"
                f"SL Guide: **{sl_estimate:.2f}** ({sl_estimate:.1f} pts) — Adjust: {sl_adjust}x\n"
                f"TP Guide: **{tp_estimate:.2f}** ({tp_estimate:.1f} pts) — Adjust: {tp_adjust}x\n"
                f"R:R Ratio: **{rr_estimate:.1f}:1**"
            ),
            "inline": False,
        })

    # SPX/SPY levels
    levels_ctx = ctx.get("levels_ctx")
    if levels_ctx and levels_ctx.hits:
        hit_lines = []
        for h in levels_ctx.hits:
            pivot_tag = " **[PIVOT]**" if h.is_pivot else ""
            hit_lines.append(
                f"`{'P' if h.is_pivot else 'L'}` "
                f"{h.instrument} {h.price}{pivot_tag} "
                f"— {h.distance:.2f}pts, price {h.direction}"
            )
        if levels_ctx.pivot_acting_as:
            hit_lines.append(f"Pivot acting as: **{levels_ctx.pivot_acting_as.upper()}**")
        fields.append({
            "name":   f"SPX/SPY levels (+{ctx.get('ext_score',0)} score boost)",
            "value":  "\n".join(hit_lines),
            "inline": False,
        })
    else:
        nearest = ctx.get("nearest_levels", {})
        if nearest.get("spy_pivot") or nearest.get("spx_pivot"):
            fields.append({
                "name":   "SPX/SPY levels",
                "value":  (
                    f"Not near any level today\n"
                    f"SPY pivot: **{nearest.get('spy_pivot','N/A')}**  "
                    f"SPX pivot: **{nearest.get('spx_pivot','N/A')}**"
                ),
                "inline": False,
            })

    return {
        "embeds": [{
            "title":       title,
            "description": description,
            "color":       COLORS.get(assessment, COLORS["unknown"]),
            "fields":      fields,
            "footer":      {
                "text": (
                    f"MNQ Agent v2 — {ts_str}  |  "
                    f"NOT FINANCIAL ADVICE  |  "
                    f"Source: {prob.get('source','?')}"
                )
            },
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }]
    }


def send_to_discord(ctx: dict, prob: dict) -> bool:
    try:
        payload = build_embed(ctx, prob)
        resp    = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        if resp.status_code == 204:
            log.info("Discord alert sent.")
            return True
        log.error(f"Discord error {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as e:
        log.error(f"Discord send exception: {e}")
        return False


def send_error_alert(message: str):
    try:
        payload = {
            "embeds": [{
                "title":       "MNQ Agent v2 — Error",
                "description": message,
                "color":       0xE74C3C,
                "footer":      {"text": "MNQ Agent v2"},
            }]
        }
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    except Exception:
        pass


def send_tp_sl_alert(alert_id: int, hit_type: str, direction: str, entry: float,
                     current: float, sl: float, tp: float, confidence: float, taken: bool):
    """Send Discord alert when TP or SL is hit."""
    try:
        taken_status = "✓ TAKEN" if taken else "✗ SKIPPED"
        emoji = "📍" if hit_type == "TP_HIT" else "⛔"
        color = 0x2ECC71 if hit_type == "TP_HIT" else 0xE74C3C  # Green for TP, Red for SL

        payload = {
            "embeds": [{
                "title":       f"{emoji} Alert #{alert_id} — {hit_type}",
                "description": f"**Status:** {taken_status}\n**Direction:** {direction}",
                "color":       color,
                "fields": [
                    {"name": "Entry", "value": f"{entry:.2f}", "inline": True},
                    {"name": "Current", "value": f"{current:.2f}", "inline": True},
                    {"name": "SL", "value": f"{sl:.2f}", "inline": True},
                    {"name": "TP", "value": f"{tp:.2f}", "inline": True},
                    {"name": "Confidence", "value": f"{confidence:.1f}", "inline": True},
                ],
                "footer":      {"text": "Auto-detected by TP/SL Monitor"},
                "timestamp":   datetime.now(TZ).isoformat(),
            }]
        }
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        log.info(f"Sent TP/SL alert for #{alert_id}: {hit_type}")
    except Exception as e:
        log.error(f"Failed to send TP/SL alert: {e}")
