# Daily SPX / SPY Key Levels
# ===========================
# Update this file each morning before the session opens.
# Format is flexible — the parser handles most common formats.
# The agent reloads this file automatically on each alert.
#
# PIVOT MAGNET LOGIC:
#   - Mark the PIVOT with the word PIVOT on the same line (e.g., 756.40 PIVOT)
#   - Pivot acts as a magnet regardless of direction (above or below)
#   - Scoring by distance:
#     * < 0.30 pts away: +2.5 points (very strong magnet)
#     * < 1.00 pts away: +1.5 points (strong magnet)
#     * < 2.00 pts away: +1.0 points (weak magnet)
#     * >= 2.00 pts away: +0.0 points (no magnet effect)
#   - Direction bonus: +0.5 if sweep aligns with SPY position vs pivot
#       (LONG sweep + SPY above pivot = bullish alignment)
#       (SHORT sweep + SPY below pivot = bearish alignment)
#
# OTHER LEVELS:
#   - Only count if price is within 0.30 pts (used as support/resistance areas)
#   - Each hit adds +0.5 points
#
# Usage:
#   - Copy your daily levels message and paste below
#   - Mark ONE level with PIVOT (preferably your key support/resistance)
#   - Replace previous day's values
#   - Save the file — agent picks it up on next alert automatically

DATE = "2026-06-08"

# ── SPY levels ────────────────────────────────────────────
# Mark the PIVOT with the word PIVOT on the same line
# Example: 522.10 PIVOT
SPY = """
767.50
766.00
764.00
761.50
760.25
758.30
757.20
756.50
754.00 PIVOT
752.20
751.50
749.60
747.00
744.80
743.20
"""

# ── SPX levels ────────────────────────────────────────────
# Mark the PIVOT with the word PIVOT on the same line
SPX = """
7621
7608
7598
7505
7570
7562
7551
7536
7530
7516
7507
7500
7484
7478
"""
