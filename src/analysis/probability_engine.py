"""
Component 4 — Claude Probability Engine (MTF Edition)
=======================================================
Sends full multi-timeframe context to Claude and gets back
a structured probability assessment with reasoning.
"""

import json
import logging
import requests
from src.data.config import ANTHROPIC_API_KEY, CLAUDE_MODEL

log = logging.getLogger("probability_engine")

TF_LABEL = {"1h": "1-Hour", "30m": "30-Min", "15m": "15-Min", "5m": "5-Min"}

SYSTEM_PROMPT = """You are an expert institutional futures trader specializing in MNQ 
(Micro E-mini Nasdaq-100) liquidity sweep setups using multi-timeframe analysis.

You receive a top-down market picture covering 1-Hour, 30-Min, 15-Min, and 5-Min 
timeframes. Your job is to evaluate whether all timeframes tell a coherent story 
and return a JSON probability assessment.

Return a JSON object with exactly these keys:
- probability: integer 0-100 (probability of price reaching the TP target)
- confidence: "low" | "medium" | "high"
- assessment: "skip" | "watch" | "take"
- reasoning: string (2-4 sentences — reference the MTF picture specifically)
- key_risk: string (main reason this trade could fail)
- tp_adjust: float (TP multiplier, e.g. 1.0 = no change, 1.2 = widen, 0.8 = tighten)
- sl_adjust: float (SL multiplier)

Calibration guidelines:
- 4/4 TFs aligned + sweep at key level + strong volume → 68-75%
- 3/4 TFs aligned + good conditions → 55-67%
- 2/4 TFs aligned → almost always "skip", max 45%
- Almost never exceed 78% — futures markets are uncertain
- A mediocre setup scores 40-52%
- Be especially generous on confluence when 1H trend strongly agrees

For TP/SL adjustments:
- When 1H trend is strongly aligned, consider tp_adjust 1.1-1.3 (ride the trend)
- When HTF is mixed or uncertain, tighten to sl_adjust 0.8-0.9
- Near a major SPX/SPY level in the trade direction, tp_adjust 1.1

Always respond with ONLY valid JSON. No preamble, no markdown."""


def build_prompt(ctx: dict) -> str:
    sweep    = ctx.get("sweep") or {}
    conds    = ctx.get("conditions", {})
    vol      = ctx.get("vol_stats", {})
    trends   = ctx.get("trends", {})
    align    = ctx.get("alignment", {})
    levels   = ctx.get("session_levels", [])

    # ── Timeframe table ───────────────────────────────────
    tf_lines = []
    for tf in ["1h", "30m", "15m", "5m"]:
        info     = trends.get(tf, {})
        trend    = info.get("trend", "unknown").upper()
        ema      = info.get("ema", 0)
        close    = info.get("close", 0)
        agrees   = align.get("detail", {}).get(tf, False)
        mark     = "ALIGNED" if agrees else "DIVERGENT"
        atr_key  = f"atr_{tf}" if tf != "1h" else "atr_1h"
        atr_val  = ctx.get(atr_key, ctx.get("atr", 0))
        tf_lines.append(
            f"  {TF_LABEL.get(tf, tf):<10} trend={trend:<5}  "
            f"EMA={ema:.2f}  close={close:.2f}  ATR={atr_val:.2f}  [{mark}]"
        )
    tf_table = "\n".join(tf_lines)

    # ── Conditions ────────────────────────────────────────
    cond_str = "\n".join(
        f"  {k}: {'YES' if v else 'NO'}" for k, v in conds.items()
    )
    ext_cond_str = "\n".join(
        f"  {k}: {'YES' if v else 'NO'}"
        for k, v in ctx.get("ext_conditions", {}).items()
    )

    # ── Session levels ────────────────────────────────────
    level_str = "\n".join(
        f"  - {l['date']}: H={l['high']} L={l['low']}" for l in levels[:3]
    ) or "  none available"

    poc_str = "\n".join(
        f"  - {p['date']}: POC={p['poc']:.2f}"
        for p in ctx.get("session_pocs", [])[:5]
    ) or "  none available"

    # ── SPX/SPY ───────────────────────────────────────────
    levels_ctx = ctx.get("levels_ctx")
    nearest    = ctx.get("nearest_levels", {})
    if levels_ctx and levels_ctx.hits:
        lvl_summary = levels_ctx.summary
        pivot_str   = (
            f"\n  Pivot acting as: {levels_ctx.pivot_acting_as.upper()}"
            if levels_ctx.pivot_acting_as else ""
        )
    else:
        lvl_summary = "Not near any SPX/SPY key levels"
        pivot_str   = ""

    bars_info = ctx.get("bars_available", {})
    bars_str  = "  " + "  ".join(
        f"{tf}={cnt}" for tf, cnt in bars_info.items()
    )

    return f"""MNQ LIQUIDITY SWEEP — MULTI-TIMEFRAME ANALYSIS

Direction:     {ctx.get('direction','unknown').upper()}
Trigger TF:    {ctx.get('trigger_tf','?').upper()} bar close
Current price: {ctx.get('current_price', 0):.2f}
Timestamp:     {ctx.get('timestamp', 'unknown')}
RTH session:   {'YES' if ctx.get('is_rth') else 'NO (extended hours)'}

TIMEFRAME ALIGNMENT  ({align.get('aligned',0)}/{align.get('total',4)} aligned — need {3}+):
{tf_table}

SWEEP DETAILS (detected on {ctx.get('trigger_tf','?').upper()}):
  Level type:   {sweep.get('level_type', 'N/A')}
  Level price:  {sweep.get('level_price', 'N/A')}
  Level date:   {sweep.get('level_date', 'N/A')}
  Sweep size:   {sweep.get('sweep_size', 'N/A')} pts beyond level
  Close price:  {sweep.get('close_price', 'N/A')}

MARKET CONTEXT (5m bars):
  VWAP (RTH):  {ctx.get('vwap', 0):.2f}  (price {'above' if ctx.get('above_vwap') else 'below'}, dist={ctx.get('vwap_dist',0):.1f}pts)
  Primary POC: {ctx.get('poc_primary', 0):.2f}  (dist={ctx.get('poc_dist',0):.1f}pts, near={'YES' if ctx.get('near_poc') else 'NO'})
  Volume:      {vol.get('ratio', 0):.1f}x avg  (spike={'YES' if vol.get('spike') else 'NO'})

SPX/SPY KEY LEVELS:
  Active: {lvl_summary}{pivot_str}
  Nearest above (SPY): {nearest.get('spy_above',[])}
  Nearest below (SPY): {nearest.get('spy_below',[])}
  Score boost: +{ctx.get('ext_score',0)}

PRIOR SESSION POCs (30m-based):
{poc_str}

PRIOR SESSION H/L LEVELS (from 1H bars):
{level_str}

CORE CONDITIONS ({ctx.get('base_score',0)}/{len(conds)} met):
{cond_str}

SPX/SPY CONDITIONS (bonus):
{ext_cond_str}

TOTAL CONFLUENCE: {ctx.get('confluence_score',0)} / {ctx.get('total_conditions',11)}
TP GUIDE: {ctx.get('tp_estimate',0):.1f} pts  |  SL GUIDE: {ctx.get('sl_estimate',0):.1f} pts  |  Base R:R: {ctx.get('rr_estimate',0):.1f}:1

Bar counts:{bars_str}

{ctx.get('historical_context', '')}

Analyse this multi-timeframe setup. Weight 1H trend heavily — it defines the day's bias.
Use the historical performance data above to calibrate your probability assessment.
Return your assessment as JSON only."""


def get_probability(ctx: dict) -> dict:
    if not ctx:
        return _fallback_assessment("No context")

    prompt  = build_prompt(ctx)
    headers = {
        "x-api-key":         ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type":      "application/json",
    }
    payload = {
        "model":      CLAUDE_MODEL,
        "max_tokens": 600,
        "system":     SYSTEM_PROMPT,
        "messages":   [{"role": "user", "content": prompt}],
    }

    try:
        log.info("Calling Claude API for MTF probability assessment...")
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()

        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block["text"]

        clean  = text.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(clean)

        for key in ["probability", "confidence", "assessment", "reasoning", "key_risk"]:
            if key not in result:
                result[key] = "unknown"

        result["source"] = "claude"
        log.info(
            f"Claude: {result.get('probability')}% — "
            f"{result.get('assessment')} ({result.get('confidence')})"
        )
        return result

    except json.JSONDecodeError as e:
        log.error(f"Claude non-JSON response: {e} — raw: {text[:200]}")
        return _fallback_assessment("Parse error")
    except requests.RequestException as e:
        log.error(f"Claude API request failed: {e}")
        return _fallback_assessment(f"API error: {e}")
    except Exception as e:
        log.error(f"Unexpected probability engine error: {e}")
        return _fallback_assessment(str(e))


def _fallback_assessment(reason: str) -> dict:
    return {
        "probability": None,
        "confidence":  "low",
        "assessment":  "watch",
        "reasoning":   f"AI assessment unavailable ({reason}). Review manually.",
        "key_risk":    "Unable to assess automatically",
        "tp_adjust":   1.0,
        "sl_adjust":   1.0,
        "source":      "fallback",
    }
