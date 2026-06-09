# MNQ Agent v1 — Custom Skills

This directory contains custom Claude Code skills for the MNQ Trading Agent.

## 📚 Available Skills

### 1. **run-agent**
- **Trigger**: `ctrl+shift+a` or `/run-agent`
- **Purpose**: Launch the agent from VSCode
- **What it does**: 
  - Starts `python src/core/run.py`
  - Shows startup logs
  - Confirms market data is loading

### 2. **test-discord**
- **Trigger**: `ctrl+shift+t` or `/test-discord`
- **Purpose**: Verify Discord webhook is working
- **What it does**:
  - Sends test message to Discord
  - Sends example alert with all fields
  - Confirms webhook connectivity

### 3. **view-daily-report**
- **Trigger**: `ctrl+shift+r` or `/view-daily-report`
- **Purpose**: Open today's alert performance report
- **What it does**:
  - Generates report from database
  - Opens HTML report in browser
  - Shows summary stats and alert details

### 4. **analyze-alerts**
- **Trigger**: `ctrl+shift+d` or `/analyze-alerts`
- **Purpose**: Deep dive into today's alerts
- **What it does**:
  - Queries all alerts from today
  - Shows entry, SL, TP, result
  - Analyzes why alerts succeeded/failed
  - Groups by score band and direction

---

## 🛠️ How to Add a New Skill

### **Step 1: Create Skill File**
Create a new Python file in this directory:
```bash
touch analyze_pnl.py
```

### **Step 2: Define Skill Structure**
```python
# .claude/skills/analyze_pnl.py

"""
Analyze P&L by score band, direction, and time of day
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.trading.trade_journal import TradeJournal
from datetime import datetime
import pytz

tz = pytz.timezone("America/Chicago")

def analyze_pnl():
    """Main skill function"""
    journal = TradeJournal()
    
    # Your analysis logic here
    print("=" * 70)
    print("P&L Analysis by Score Band")
    print("=" * 70)
    
    # Example: get alerts and analyze
    today = datetime.now(tz).strftime("%Y-%m-%d")
    alerts = journal.get_alerts_by_date(today)
    
    # Process and display...
    print(f"Found {len(alerts)} alerts")

if __name__ == "__main__":
    analyze_pnl()
```

### **Step 3: Register Skill in settings.json**
Add to `.claude/settings.json`:
```json
"customSkills": {
  "analyze-pnl": {
    "file": ".claude/skills/analyze_pnl.py",
    "trigger": "ctrl+shift+p",
    "description": "Analyze P&L by score band and direction"
  }
}
```

### **Step 4: Use It!**
- Press `ctrl+shift+p` OR
- Type `/analyze-pnl` in Claude Code

---

## 💡 Skill Ideas for MNQ Agent

### **High Priority**
- [ ] **Auto-restart agent** — Kill and restart with one shortcut
- [ ] **Quick stats** — Show today's win rate and P&L in popup
- [ ] **Export trades** — Save alerts to CSV/Excel
- [ ] **Backtest setup** — Analyze historical performance of score bands

### **Medium Priority**
- [ ] **SPY analysis** — Show current SPY level and nearest pivots
- [ ] **Market hours check** — Is market open? When does it close?
- [ ] **Database cleanup** — Archive old alerts, compress database
- [ ] **Alert replay** — Rerun analysis on historical alerts

### **Nice to Have**
- [ ] **Email reports** — Send daily report via email
- [ ] **Slack integration** — Send alerts to Slack instead of Discord
- [ ] **Trade journal sync** — Import trades from broker API
- [ ] **Performance trends** — Weekly/monthly P&L graphs

---

## 📂 Project Structure

```
.claude/
├── settings.json          # Project configuration
├── keybindings.json       # Custom keyboard shortcuts
├── skills/
│   ├── README.md          # This file
│   ├── run_agent.py       # Skill: Launch agent
│   ├── test_discord.py    # Skill: Test webhook
│   ├── view_report.py     # Skill: Open daily report
│   └── analyze_alerts.py  # Skill: Analyze today's alerts
```

---

## 🔗 Environment Setup

All skills automatically:
- Add project root to `sys.path`
- Import necessary modules from `src/`
- Use `.env` for configuration
- Access the trade journal database

No additional setup needed!

---

## ✅ Testing a Skill

Before publishing, test locally:
```bash
cd "C:\Users\adria\Documents\AJ\MNQ Agent\mnq_v1"
python .claude/skills/your_skill.py
```

---

## 📖 Resources

- **Main README**: See `README.md` in project root
- **Database Schema**: `src/trading/trade_journal.py`
- **Configuration**: `src/data/config.py`
- **Project Rules**: `CLAUDE.md`

---

**Ready to add your first skill?** Start with something simple like a stats viewer, then build from there! 🚀
