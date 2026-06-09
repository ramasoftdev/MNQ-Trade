"""
Daily Report Generation
=======================
Generates daily trading reports with statistics, win rate analysis, and insights.
Formats for Discord, text, and HTML.
"""

import logging
from datetime import datetime
from src.trading.trade_journal import TradeJournal
import pytz

log = logging.getLogger("daily_report")
TZ = pytz.timezone("America/Chicago")

# Assessment colors for Discord embeds
ASSESSMENT_COLOR = {
    "TAKE": 0x00FF00,      # Green
    "HOLD": 0xFFFF00,      # Yellow
    "WATCH": 0xFFA500,     # Orange
    "PASS": 0xFF0000,      # Red
    "unknown": 0x808080,   # Gray
}


class DailyReport:
    """Generate daily trading reports from trade journal."""

    def __init__(self, db_path: str = None):
        """Initialize report generator with trade journal."""
        self.journal = TradeJournal(db_path)

    def generate_report(self, date_str: str = None) -> "Report":
        """
        Generate report for a specific date (ALERT-BASED METRICS).

        Args:
            date_str: "YYYY-MM-DD" (default: today)

        Returns:
            Report object with data and formatting methods
        """
        if not date_str:
            date_str = datetime.now(TZ).strftime("%Y-%m-%d")

        # Get all alerts for the day
        alerts = self.journal.get_alerts_by_date(date_str)

        return Report(
            date=date_str,
            alerts=alerts,
        )


class Report:
    """Single daily report showing ALERT PERFORMANCE metrics."""

    def __init__(self, date: str, alerts: list):
        """Initialize report with alerts data."""
        self.date = date
        self.alerts = alerts or []
        self.stats = self._calculate_alert_stats()

    def _calculate_alert_stats(self) -> dict:
        """Calculate metrics from alerts (TP hits, SL hits, win rate)."""
        total_alerts = len(self.alerts)

        tp_hits = 0
        sl_hits = 0
        manual_exits = 0
        total_pnl = 0.0
        by_direction = {}
        by_score_band = {"10+": {}, "8-10": {}, "5-8": {}, "<5": {}}

        for alert in self.alerts:
            if isinstance(alert, dict):
                exit_type = alert.get('exit_type', '')
                direction = alert.get('direction', 'unknown').upper()
                score = alert.get('confluence_score', 0)
                pnl = alert.get('pnl', 0)
            else:
                # Tuple format (index based on schema)
                exit_type = alert[12] if len(alert) > 12 else ''
                direction = (alert[2] if len(alert) > 2 else 'unknown').upper()
                score = alert[4] if len(alert) > 4 else 0
                pnl = alert[13] if len(alert) > 13 else 0

            # Count exit types
            if exit_type == 'TP_HIT':
                tp_hits += 1
            elif exit_type == 'SL_HIT':
                sl_hits += 1
            elif exit_type == 'MANUAL_EXIT':
                manual_exits += 1

            total_pnl += pnl or 0

            # By direction
            if direction not in by_direction:
                by_direction[direction] = {'total': 0, 'tp_hits': 0, 'sl_hits': 0, 'pnl': 0}
            by_direction[direction]['total'] += 1
            if exit_type == 'TP_HIT':
                by_direction[direction]['tp_hits'] += 1
            elif exit_type == 'SL_HIT':
                by_direction[direction]['sl_hits'] += 1
            by_direction[direction]['pnl'] += pnl or 0

            # By score band
            if score >= 10:
                band = "10+"
            elif score >= 8:
                band = "8-10"
            elif score >= 5:
                band = "5-8"
            else:
                band = "<5"

            if not by_score_band[band]:
                by_score_band[band] = {'total': 0, 'tp_hits': 0, 'sl_hits': 0, 'pnl': 0}
            by_score_band[band]['total'] += 1
            if exit_type == 'TP_HIT':
                by_score_band[band]['tp_hits'] += 1
            elif exit_type == 'SL_HIT':
                by_score_band[band]['sl_hits'] += 1
            by_score_band[band]['pnl'] += pnl or 0

        # Calculate win rates
        tp_sl_total = tp_hits + sl_hits
        win_rate_pct = (tp_hits / tp_sl_total * 100) if tp_sl_total > 0 else 0

        # Add win rates to direction stats
        for direction in by_direction:
            tp_sl = by_direction[direction]['tp_hits'] + by_direction[direction]['sl_hits']
            by_direction[direction]['win_rate'] = (by_direction[direction]['tp_hits'] / tp_sl * 100) if tp_sl > 0 else 0

        # Add win rates to score band stats
        for band in by_score_band:
            if by_score_band[band]:
                tp_sl = by_score_band[band]['tp_hits'] + by_score_band[band]['sl_hits']
                by_score_band[band]['win_rate'] = (by_score_band[band]['tp_hits'] / tp_sl * 100) if tp_sl > 0 else 0

        return {
            'total_alerts': total_alerts,
            'tp_hits': tp_hits,
            'sl_hits': sl_hits,
            'manual_exits': manual_exits,
            'win_rate_pct': win_rate_pct,
            'total_pnl': total_pnl,
            'avg_pnl_per_alert': total_pnl / total_alerts if total_alerts > 0 else 0,
            'by_direction': by_direction,
            'by_score_band': {k: v for k, v in by_score_band.items() if v},
        }

    def to_text(self) -> str:
        """Format report as plain text (ALERT-BASED METRICS)."""
        lines = []
        lines.append("=" * 70)
        lines.append(f"  MNQ TRADING AGENT — DAILY REPORT (ALERT PERFORMANCE)")
        lines.append(f"  {self.date}")
        lines.append("=" * 70)
        lines.append("")

        # Summary stats
        lines.append("SUMMARY — ALERT STATISTICS")
        lines.append("-" * 70)
        lines.append(f"  Total Alerts:      {self.stats['total_alerts']}")
        lines.append(f"  TP Hits:           {self.stats['tp_hits']}")
        lines.append(f"  SL Hits:           {self.stats['sl_hits']}")
        lines.append(f"  Manual Exits:      {self.stats['manual_exits']}")
        lines.append(f"  Win Rate (TP%):    {self.stats['win_rate_pct']:.1f}%")
        lines.append(f"  Total P&L:         ${self.stats['total_pnl']:,.2f}")
        lines.append(f"  Avg P&L / Alert:   ${self.stats['avg_pnl_per_alert']:,.2f}")
        lines.append("")

        # By direction
        if self.stats.get("by_direction"):
            lines.append("ALERT PERFORMANCE BY DIRECTION")
            lines.append("-" * 70)
            for direction, data in self.stats["by_direction"].items():
                lines.append(
                    f"  {direction:6} — {data['total']} alerts, "
                    f"{data['tp_hits']} TP hits, {data['sl_hits']} SL hits, "
                    f"{data['win_rate']:.1f}% WR, ${data['pnl']:,.2f} P&L"
                )
            lines.append("")

        # By confluence band
        if self.stats.get("by_score_band"):
            lines.append("ALERT PERFORMANCE BY CONFLUENCE SCORE")
            lines.append("-" * 70)
            for band in ["10+", "8-10", "5-8", "<5"]:
                if band in self.stats["by_score_band"]:
                    data = self.stats["by_score_band"][band]
                    lines.append(
                        f"  {band:4} — {data['total']} alerts, "
                        f"{data['tp_hits']} TP, {data['sl_hits']} SL, "
                        f"{data['win_rate']:.1f}% WR, ${data['pnl']:,.2f} P&L"
                    )
            lines.append("")

        # Footer
        lines.append("=" * 70)
        lines.append(f"Generated: {datetime.now(pytz.timezone('America/Chicago')).strftime('%Y-%m-%d %H:%M CT')}")
        lines.append("MNQ Trading Agent v2 — Alert Performance Report")
        lines.append("=" * 70)

        return "\n".join(lines)

    def to_discord_embed(self) -> dict:
        """Format report as Discord embed (ALERT-BASED METRICS)."""

        # Determine color based on win rate
        win_rate = self.stats["win_rate_pct"]
        if win_rate >= 60:
            color = 0x00FF00  # Green — strong win rate
        elif win_rate >= 40:
            color = 0xFFFF00  # Yellow — moderate win rate
        else:
            color = 0xFF0000  # Red — weak win rate

        # Build description
        description_lines = []
        description_lines.append(
            f"**{self.stats['total_alerts']} alerts** | "
            f"**{self.stats['tp_hits']} TP hits** | "
            f"**{self.stats['sl_hits']} SL hits**"
        )
        description_lines.append("")
        description_lines.append(
            f"📊 **Win Rate: {self.stats['win_rate_pct']:.1f}%** | "
            f"💰 **P&L: ${self.stats['total_pnl']:,.2f}**"
        )

        # Build fields
        fields = []

        # TP/SL breakdown
        fields.append({
            "name": "Alert Outcomes",
            "value": (
                f"✓ TP Hits: **{self.stats['tp_hits']}** | "
                f"✗ SL Hits: **{self.stats['sl_hits']}** | "
                f"⊘ Manual: **{self.stats['manual_exits']}**"
            ),
            "inline": True,
        })

        # Average P&L
        fields.append({
            "name": "Average P&L",
            "value": f"${self.stats['avg_pnl_per_alert']:,.2f} per alert",
            "inline": True,
        })

        # Direction breakdown
        if self.stats.get("by_direction"):
            direction_lines = []
            for direction, data in sorted(self.stats["by_direction"].items()):
                direction_lines.append(
                    f"**{direction}**: {data['total']} alerts, {data['tp_hits']} TP, {data['win_rate']:.0f}% WR, ${data['pnl']:,.0f}"
                )
            if direction_lines:
                fields.append({
                    "name": "By Direction",
                    "value": "\n".join(direction_lines),
                    "inline": False,
                })

        # Confluence band breakdown
        if self.stats.get("by_score_band"):
            band_lines = []
            for band in ["10+", "8-10", "5-8", "<5"]:
                if band in self.stats["by_score_band"]:
                    data = self.stats["by_score_band"][band]
                    band_lines.append(
                        f"**{band}**: {data['total']} alerts, {data['tp_hits']} TP hits, {data['win_rate']:.0f}% WR"
                    )
            if band_lines:
                fields.append({
                    "name": "By Confluence Band",
                    "value": "\n".join(band_lines),
                    "inline": False,
                })

        return {
            "embeds": [{
                "title": f"MNQ Daily Report — {self.date}",
                "description": "\n".join(description_lines),
                "color": color,
                "fields": fields,
                "footer": {
                    "text": "MNQ Agent v2 — Alert Performance Report"
                },
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }]
        }

    def to_html(self, output_path: str = None) -> str:
        """
        Format report as HTML file (ALERT-BASED METRICS).

        Args:
            output_path: Where to save HTML (default: ./reports/report_{date}.html)

        Returns:
            Path to generated file
        """
        if not output_path:
            from pathlib import Path
            reports_dir = Path(__file__).parent / "reports"
            reports_dir.mkdir(exist_ok=True)
            output_path = str(reports_dir / f"report_{self.date}.html")

        # Determine color based on win rate
        win_rate = self.stats["win_rate_pct"]
        if win_rate >= 60:
            header_color = "#00a651"  # Green
        elif win_rate >= 40:
            header_color = "#ffc107"  # Yellow
        else:
            header_color = "#e81123"  # Red

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>MNQ Daily Report — {self.date}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 900px;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: white;
            background: {header_color};
            border-bottom: none;
            padding: 15px;
            border-radius: 4px;
            margin: -20px -20px 20px -20px;
        }}
        h2 {{
            color: #333;
            border-bottom: 2px solid #0078d4;
            padding-bottom: 10px;
            margin-top: 30px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin: 20px 0;
        }}
        .stat-box {{
            background: #f9f9f9;
            padding: 15px;
            border-radius: 4px;
            border-left: 4px solid #0078d4;
        }}
        .stat-label {{
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #333;
        }}
        .positive {{ color: #00a651; }}
        .negative {{ color: #e81123; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th {{
            background: #0078d4;
            color: white;
            padding: 10px;
            text-align: left;
        }}
        td {{
            padding: 10px;
            border-bottom: 1px solid #ddd;
        }}
        tr:hover {{
            background: #f0f0f0;
        }}
        .footer {{
            text-align: center;
            color: #999;
            margin-top: 30px;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>MNQ Daily Report — {self.date} (Alert Performance)</h1>

        <div class="summary">
            <div class="stat-box">
                <div class="stat-label">Total Alerts</div>
                <div class="stat-value">{self.stats['total_alerts']}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">TP Hits</div>
                <div class="stat-value positive">{self.stats['tp_hits']}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">SL Hits</div>
                <div class="stat-value negative">{self.stats['sl_hits']}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Win Rate</div>
                <div class="stat-value" style="color: {header_color}">{self.stats['win_rate_pct']:.1f}%</div>
            </div>
        </div>

        <h2>Alert Performance By Direction</h2>
        <table>
            <tr>
                <th>Direction</th>
                <th>Total Alerts</th>
                <th>TP Hits</th>
                <th>SL Hits</th>
                <th>Win Rate</th>
                <th>Total P&L</th>
            </tr>
"""

        if self.stats.get("by_direction"):
            for direction, data in sorted(self.stats["by_direction"].items()):
                pnl_class = "positive" if data['pnl'] > 0 else "negative"
                html += f"""
            <tr>
                <td><strong>{direction}</strong></td>
                <td>{data['total']}</td>
                <td>{data['tp_hits']}</td>
                <td>{data['sl_hits']}</td>
                <td>{data['win_rate']:.1f}%</td>
                <td class="{pnl_class}">${data['pnl']:,.2f}</td>
            </tr>
"""

        html += """
        </table>

        <h2>Alert Performance By Confluence Score</h2>
        <table>
            <tr>
                <th>Score Band</th>
                <th>Total Alerts</th>
                <th>TP Hits</th>
                <th>SL Hits</th>
                <th>Win Rate</th>
                <th>Total P&L</th>
            </tr>
"""

        if self.stats.get("by_score_band"):
            for band in ["10+", "8-10", "5-8", "<5"]:
                if band in self.stats["by_score_band"]:
                    data = self.stats["by_score_band"][band]
                    pnl_class = "positive" if data['pnl'] > 0 else "negative"
                    html += f"""
            <tr>
                <td><strong>{band}</strong></td>
                <td>{data['total']}</td>
                <td>{data['tp_hits']}</td>
                <td>{data['sl_hits']}</td>
                <td>{data['win_rate']:.1f}%</td>
                <td class="{pnl_class}">${data['pnl']:,.2f}</td>
            </tr>
"""

        html += """
        </table>

        <h2>Alert Details</h2>
        <table>
            <tr>
                <th>Time</th>
                <th>Direction</th>
                <th>Score</th>
                <th>Entry</th>
                <th>SL</th>
                <th>TP</th>
                <th>Result</th>
                <th>P&L</th>
            </tr>
"""

        # Add individual alerts
        if self.alerts:
            for alert in sorted(self.alerts, key=lambda a: a.get('timestamp', '') if isinstance(a, dict) else a[1], reverse=True):
                if isinstance(alert, dict):
                    # Extract time in HH:MM format
                    full_timestamp = alert.get('timestamp', '')
                    timestamp = full_timestamp[11:16] if len(full_timestamp) > 16 else "??:??"  # Extract HH:MM from ISO timestamp

                    direction = alert.get('direction', '?').upper()
                    score = alert.get('confluence_score', 0)
                    entry = alert.get('current_price', 0)
                    sl = alert.get('sl_estimate', 0)
                    tp = alert.get('tp_estimate', 0)
                    exit_type = alert.get('exit_type', 'PENDING')
                    pnl = alert.get('pnl', 0)
                else:
                    # Tuple format (adjust indices as needed)
                    full_timestamp = alert[0] if len(alert) > 0 else ''
                    timestamp = full_timestamp[11:16] if len(full_timestamp) > 16 else "??:??"  # Extract HH:MM

                    direction = (alert[2] if len(alert) > 2 else '?').upper()
                    score = alert[4] if len(alert) > 4 else 0
                    entry = alert[5] if len(alert) > 5 else 0
                    sl = alert[14] if len(alert) > 14 else 0  # Adjust based on actual schema
                    tp = alert[15] if len(alert) > 15 else 0
                    exit_type = alert[12] if len(alert) > 12 else 'PENDING'
                    pnl = alert[16] if len(alert) > 16 else 0

                # Determine result color
                if exit_type == 'TP_HIT':
                    result_color = "#00a651"
                    result_symbol = "✓ TP"
                elif exit_type == 'SL_HIT':
                    result_color = "#e81123"
                    result_symbol = "✗ SL"
                elif exit_type == 'MANUAL_EXIT':
                    result_color = "#ffc107"
                    result_symbol = "⊘ MANUAL"
                else:
                    result_color = "#999"
                    result_symbol = "PENDING"

                pnl_class = "positive" if pnl > 0 else "negative" if pnl < 0 else ""

                html += f"""
            <tr>
                <td>{timestamp}</td>
                <td><strong>{direction}</strong></td>
                <td>{score:.1f}</td>
                <td>${entry:.2f}</td>
                <td>${sl:.2f}</td>
                <td>${tp:.2f}</td>
                <td style="color: {result_color}"><strong>{result_symbol}</strong></td>
                <td class="{pnl_class}">${pnl:,.2f}</td>
            </tr>
"""

        html += """
        </table>

        <div class="footer">
            <p>Generated by MNQ Trading Agent v2</p>
            <p>Alert Performance Report System</p>
        </div>
    </div>
</body>
</html>
"""

        with open(output_path, "w") as f:
            f.write(html)

        log.info(f"HTML report generated: {output_path}")
        return output_path
