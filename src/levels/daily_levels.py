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

DATE = "2026-06-09"

# ── SPY levels ────────────────────────────────────────────
# Mark the PIVOT with the word PIVOT on the same line
# Example: 522.10 PIVOT
SPY = """
752.80
750.30
749.70
747.50
746.40
745.50
745.20
744.20
742.80 PIVOT
741.00
738.20
736.80
734.00
731.60
729.50
725.40
725.00
"""

# ── SPX levels ────────────────────────────────────────────
# Mark the PIVOT with the word PIVOT on the same line
SPX = """
7508
7506
7499
7488
7480
7467
7440
7419
7413
7395
7388
7373
7368
7356
7331
"""
