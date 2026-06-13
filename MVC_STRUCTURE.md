# MVC Architecture — MNQ Trading Agent

## Overview

The project has been refactored into a clean **Model-View-Controller** architecture with supporting services.

```
src/
├── models/                      [MODEL LAYER]
│   ├── __init__.py
│   ├── alert.py                 Alert data structure
│   └── trade.py                 Trade data structure
│
├── database/                    [DATA ACCESS LAYER]
│   ├── __init__.py
│   ├── alert_db.py              Alert database operations
│   └── trade_db.py              Trade database operations
│
├── controllers/                 [CONTROLLER LAYER]
│   ├── __init__.py
│   ├── alert_controller.py      Alert business logic
│   ├── trade_controller.py      Trade business logic
│   └── monitor_controller.py    Monitoring orchestration
│
├── views/                       [VIEW LAYER]
│   ├── __init__.py
│   ├── discord_view.py          Discord message formatting
│   └── report_view.py           Report generation
│
├── services/                    [SERVICE LAYER]
│   ├── __init__.py
│   └── price_service.py         Price data fetching
│
├── core/                        [ORCHESTRATORS]
│   ├── agent.py                 Main agent (to be updated)
│   ├── monitor.py               Monitor loop (to be updated)
│   └── run.py
│
├── analysis/                    [EXISTING - unchanged]
├── data/
├── reporting/
└── trading/

```

---

## Architecture Flow

### Creating an Alert
```
Agent.on_bar_close() detects sweep
    ↓
AlertController.create_alert(alert_data)
    ├─ Creates Alert model
    ├─ Validates with alert.is_valid()
    ├─ Calls AlertDatabase.save()
    └─ Returns Alert with ID
    ↓
DiscordView.send_alert(alert)
    └─ Sends to Discord
```

### Detecting and Recording Exits
```
Monitor fetches current price
    ↓
MonitorController.check_pending_alerts(price)
    ├─ Gets pending alerts from AlertDatabase
    └─ For each alert:
        ↓
        TradeController.check_and_record_exit(alert_id, price)
            ├─ Calls _determine_exit() (SL or TP hit?)
            ├─ Calls _calculate_pnl()
            ├─ Creates Trade model
            ├─ Calls TradeDatabase.save()
            └─ Updates AlertDatabase.update_status()
            ↓
            DiscordView.send_exit(trade, alert)
                └─ Sends exit notification to Discord
```

### Generating Reports
```
Agent/Scripts call ReportView methods
    ↓
ReportView.generate_alert_summary(alerts)
    └─ Returns statistics dict
    ↓
ReportView.generate_text_report(alerts, trades)
    └─ Returns formatted text
    ↓
ReportView.generate_html_report(alerts, trades)
    └─ Returns HTML content
```

---

## Key Components

### Models (Data Structures)
- **Alert**: Represents a detected sweep alert
  - Properties: direction, entry_price, stop_loss, take_profit, confluence_score, etc.
  - Methods: is_valid(), has_targets(), to_dict()

- **Trade**: Represents a completed trade
  - Properties: entry_price, exit_price, pnl, pnl_percent, exit_type, etc.
  - Methods: is_valid(), is_win, is_loss, is_break_even

### Database Layer
- **AlertDatabase**: Save/load Alert models
  - Methods: save(), get_by_id(), get_pending(), get_by_date(), update_status()

- **TradeDatabase**: Save/load Trade models
  - Methods: save(), get_by_id(), get_by_alert_id(), get_by_date(), get_by_exit_type()

### Controllers (Business Logic)
- **AlertController**: Alert management
  - Methods: create_alert(), get_alert(), get_pending_alerts(), update_alert_status()

- **TradeController**: Trade handling
  - Methods: check_and_record_exit(), _determine_exit(), _calculate_pnl()

- **MonitorController**: Monitoring orchestration
  - Methods: check_pending_alerts(), get_trade_summary()

### Views (Presentation)
- **DiscordView**: Discord notifications
  - Methods: send_alert(), send_exit(), send_error()

- **ReportView**: Report generation
  - Methods: generate_alert_summary(), generate_trade_summary(), generate_text_report(), generate_html_report()

### Services (Helpers)
- **PriceService**: Market data
  - Methods: get_mnq_price(), get_spy_price(), get_spx_price(), get_price()

---

## Benefits

✅ **Separation of Concerns**: Each layer has a single responsibility
✅ **Testability**: Easy to unit test controllers and views independently
✅ **Reusability**: Controllers can be used by multiple views (Discord, Email, Slack, etc.)
✅ **Maintainability**: Clear structure, easy to find code
✅ **Scalability**: Easy to add new features without breaking existing code
✅ **Data Integrity**: Models validate data before persistence

---

## Next Steps (Phase 6: Update Orchestrators)

The Agent and Monitor need to be updated to use the new MVC controllers instead of calling database methods directly.

### Update agent.py
Replace direct database calls with controller calls:
```python
# Old (tightly coupled)
alert_id = journal.log_alert(alert_data)

# New (MVC)
alert_ctrl = AlertController()
alert = alert_ctrl.create_alert(alert_data)
```

### Update monitor.py
Use the new MonitorController:
```python
# Old
pending = journal.get_open_alerts_for_monitoring()
for alert in pending:
    hit_type, price = journal.check_and_record_tp_sl_hit(...)

# New
monitor_ctrl = MonitorController(trade_ctrl)
trades = monitor_ctrl.check_pending_alerts(current_price)
for trade in trades:
    discord_view.send_exit(trade, alert)
```

---

## Testing the MVC Structure

```bash
# Test models
python -c "
from src.models.alert import Alert
a = Alert('LONG', 29766.75, 6.5)
print('Alert valid:', a.is_valid())
print('Alert:', a)
"

# Test database layer
python -c "
from src.database.alert_db import AlertDatabase
db = AlertDatabase()
alerts = db.get_pending()
print(f'Pending alerts: {len(alerts)}')
"

# Test controllers
python -c "
from src.controllers.alert_controller import AlertController
ctrl = AlertController()
alerts = ctrl.get_pending_alerts()
print(f'Pending alerts from controller: {len(alerts)}')
"
```

---

## Migration Checklist

- [x] Create Models (Alert, Trade)
- [x] Create Database Layer (AlertDatabase, TradeDatabase)
- [x] Create Controllers (AlertController, TradeController, MonitorController)
- [x] Create Views (DiscordView, ReportView)
- [x] Create Services (PriceService)
- [ ] Update agent.py to use AlertController and DiscordView
- [ ] Update monitor.py to use MonitorController and DiscordView
- [ ] Test startup (agent + monitor)
- [ ] Verify Discord alerts are still working
- [ ] Generate and verify reports

---

## Command Reference (Unchanged)

Users run the same commands as before:

```bash
# Terminal 1: Start Agent
python src/core/run.py

# Terminal 2: Start Monitor
python src/monitoring/monitor.py

# View Report
Ctrl+Shift+R

# Analyze Alerts
Ctrl+Shift+D
```

The MVC refactoring is **internal** — the interface stays the same! ✨

---

**Status**: Phase 1-5 Complete ✅
**Next**: Phase 6 — Update agent.py and monitor.py to use new MVC structure

Ready to update the orchestrators? 🚀
