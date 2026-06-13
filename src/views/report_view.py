"""Report presentation layer."""

import logging
from typing import List
from datetime import datetime

from src.models.alert import Alert
from src.models.trade import Trade

log = logging.getLogger("report_view")


class ReportView:
    """Handles report generation and formatting."""

    @staticmethod
    def generate_alert_summary(alerts: List[Alert]) -> dict:
        """Generate summary statistics from alerts."""
        if not alerts:
            return {
                "total_alerts": 0,
                "by_direction": {},
                "by_assessment": {},
                "avg_score": 0,
            }

        by_direction = {
            "LONG": len([a for a in alerts if a.direction == "LONG"]),
            "SHORT": len([a for a in alerts if a.direction == "SHORT"]),
        }

        by_assessment = {
            "take": len([a for a in alerts if a.assessment == "take"]),
            "watch": len([a for a in alerts if a.assessment == "watch"]),
            "skip": len([a for a in alerts if a.assessment == "skip"]),
        }

        avg_score = sum(a.confluence_score for a in alerts) / len(alerts) if alerts else 0

        return {
            "total_alerts": len(alerts),
            "by_direction": by_direction,
            "by_assessment": by_assessment,
            "avg_score": round(avg_score, 2),
        }

    @staticmethod
    def generate_trade_summary(trades: List[Trade]) -> dict:
        """Generate summary statistics from trades."""
        if not trades:
            return {
                "total_trades": 0,
                "total_pnl": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0,
                "avg_pnl": 0,
                "tp_hits": 0,
                "sl_hits": 0,
            }

        total_pnl = sum(t.pnl for t in trades)
        wins = sum(1 for t in trades if t.result == "WIN")
        losses = sum(1 for t in trades if t.result == "LOSS")
        tp_hits = sum(1 for t in trades if t.exit_type == "TP_HIT")
        sl_hits = sum(1 for t in trades if t.exit_type == "SL_HIT")
        win_rate = (wins / len(trades) * 100) if trades else 0
        avg_pnl = total_pnl / len(trades) if trades else 0

        return {
            "total_trades": len(trades),
            "total_pnl": round(total_pnl, 2),
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 1),
            "avg_pnl": round(avg_pnl, 2),
            "tp_hits": tp_hits,
            "sl_hits": sl_hits,
        }

    @staticmethod
    def generate_text_report(alerts: List[Alert], trades: List[Trade]) -> str:
        """Generate text report."""
        alert_summary = ReportView.generate_alert_summary(alerts)
        trade_summary = ReportView.generate_trade_summary(trades)

        date_str = datetime.now().strftime("%Y-%m-%d")

        report = f"""
{'=' * 70}
MNQ TRADING AGENT — DAILY REPORT {date_str}
{'=' * 70}

ALERTS GENERATED
{'-' * 70}
Total Alerts:     {alert_summary['total_alerts']}
LONG:             {alert_summary['by_direction'].get('LONG', 0)}
SHORT:            {alert_summary['by_direction'].get('SHORT', 0)}
Avg Score:        {alert_summary['avg_score']}

Assessment Breakdown:
  Take:  {alert_summary['by_assessment'].get('take', 0)}
  Watch: {alert_summary['by_assessment'].get('watch', 0)}
  Skip:  {alert_summary['by_assessment'].get('skip', 0)}

TRADES COMPLETED
{'-' * 70}
Total Trades:     {trade_summary['total_trades']}
Wins:             {trade_summary['wins']}
Losses:           {trade_summary['losses']}
Win Rate:         {trade_summary['win_rate']:.1f}%

TP Hits:          {trade_summary['tp_hits']}
SL Hits:          {trade_summary['sl_hits']}

Total P&L:        ${trade_summary['total_pnl']:.2f}
Avg P&L:          ${trade_summary['avg_pnl']:.2f}

{'=' * 70}
"""
        return report

    @staticmethod
    def generate_html_report(alerts: List[Alert], trades: List[Trade]) -> str:
        """Generate HTML report."""
        alert_summary = ReportView.generate_alert_summary(alerts)
        trade_summary = ReportView.generate_trade_summary(trades)

        date_str = datetime.now().strftime("%Y-%m-%d")

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>MNQ Daily Report — {date_str}</title>
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
            background: #e81123;
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
        <h1>MNQ Daily Report — {date_str}</h1>

        <h2>Alerts Summary</h2>
        <div class="summary">
            <div class="stat-box">
                <div class="stat-label">Total Alerts</div>
                <div class="stat-value">{alert_summary['total_alerts']}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">LONG</div>
                <div class="stat-value">{alert_summary['by_direction'].get('LONG', 0)}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">SHORT</div>
                <div class="stat-value">{alert_summary['by_direction'].get('SHORT', 0)}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Avg Score</div>
                <div class="stat-value">{alert_summary['avg_score']}</div>
            </div>
        </div>

        <h2>Trade Summary</h2>
        <div class="summary">
            <div class="stat-box">
                <div class="stat-label">Total Trades</div>
                <div class="stat-value">{trade_summary['total_trades']}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Win Rate</div>
                <div class="stat-value" style="color: {'#00a651' if trade_summary['win_rate'] >= 50 else '#e81123'}">{trade_summary['win_rate']:.1f}%</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Total P&L</div>
                <div class="stat-value" style="color: {'#00a651' if trade_summary['total_pnl'] >= 0 else '#e81123'}">${trade_summary['total_pnl']:.2f}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Avg P&L</div>
                <div class="stat-value" style="color: {'#00a651' if trade_summary['avg_pnl'] >= 0 else '#e81123'}">${trade_summary['avg_pnl']:.2f}</div>
            </div>
        </div>

        <h2>Trade Details</h2>
        <table>
            <tr>
                <th>Alert ID</th>
                <th>Direction</th>
                <th>Entry</th>
                <th>Exit</th>
                <th>Type</th>
                <th>P&L</th>
                <th>Result</th>
            </tr>
"""
        for trade in trades:
            pnl_color = "positive" if trade.pnl >= 0 else "negative"
            html += f"""
            <tr>
                <td>{trade.alert_id}</td>
                <td><strong>{trade.direction}</strong></td>
                <td>${trade.entry_price:.2f}</td>
                <td>${trade.exit_price:.2f}</td>
                <td>{trade.exit_type}</td>
                <td class="{pnl_color}">${trade.pnl:.2f}</td>
                <td><strong>{trade.result}</strong></td>
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
        return html
