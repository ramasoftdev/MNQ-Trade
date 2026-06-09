# Project Restructuring Plan — Directory Organization

## Current State

```
mnq_v2/
├── agent.py
├── config.py
├── data_fetcher.py
├── spy_fetcher.py
├── context_analyzer.py
├── levels_analyzer.py
├── spy_levels_analyzer.py
├── probability_engine.py
├── discord_formatter.py
├── trade_journal.py
├── daily_report.py
├── report_scheduler.py
├── fill_trade.py
├── daily_levels.py
├── *.md files (6+ docs)
├── tests/
├── reports/
└── __pycache__/
```

**Problems:**
- 14+ Python files in root (hard to navigate)
- Mixed concerns (data, analysis, trading, reporting)
- Documentation scattered

---

## Proposed Structure

```
mnq_v2/
│
├── src/
│   ├── __init__.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── agent.py                 (main orchestrator)
│   │   └── run.py                   (entry point)
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── data_fetcher.py          (Tradovate connection)
│   │   ├── spy_fetcher.py           (Finnhub connection)
│   │   └── config.py                (all configuration)
│   │
│   ├── levels/
│   │   ├── __init__.py
│   │   ├── daily_levels.py          (daily level definitions)
│   │   ├── levels_analyzer.py       (SPX/SPY level analysis)
│   │   └── spy_levels_analyzer.py   (SPY pivot magnet logic)
│   │
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── context_analyzer.py      (sweep, trends, confluence)
│   │   └── probability_engine.py    (Claude integration)
│   │
│   ├── trading/
│   │   ├── __init__.py
│   │   ├── trade_journal.py         (SQLite database)
│   │   └── fill_trade.py            (CLI tool for fills)
│   │
│   ├── reporting/
│   │   ├── __init__.py
│   │   ├── daily_report.py          (report generation)
│   │   ├── discord_formatter.py     (Discord alerts)
│   │   └── report_scheduler.py      (auto-scheduling)
│   │
│   └── utils/
│       ├── __init__.py
│       └── helpers.py               (common utilities)
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  (pytest fixtures)
│   │
│   ├── unit/
│   │   ├── test_data_fetcher.py
│   │   ├── test_context_analyzer.py
│   │   ├── test_levels_analyzer.py
│   │   ├── test_discord_formatter.py
│   │   ├── test_probability_engine.py
│   │   └── test_trade_journal.py
│   │
│   ├── integration/
│   │   ├── test_agent_flow.py       (end-to-end tests)
│   │   └── test_reporting.py
│   │
│   ├── fixtures/
│   │   ├── __init__.py
│   │   └── fixtures.py              (shared test data)
│   │
│   └── data/
│       ├── test_bars.py
│       └── test_levels.py
│
├── docs/
│   ├── README.md
│   ├── AGENT_DOCUMENTATION.md
│   ├── TESTING_PLAN.md
│   ├── TRADE_JOURNAL_GUIDE.md
│   ├── SPY_MAGNET_LOGIC.md
│   └── RESTRUCTURE_PLAN.md
│
├── reports/                         (auto-generated, gitignored)
│   └── report_YYYY-MM-DD.html
│
├── output/                          (exports, backups)
│   ├── csv/
│   │   └── trades_YYYY-MM-DD.csv
│   └── backups/
│       └── trades_BACKUP_*.db
│
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
├── setup.py
├── pytest.ini
│
└── scripts/
    ├── run_agent.sh                 (Unix launcher)
    ├── run_agent.bat                (Windows launcher)
    ├── run_tests.sh
    └── generate_report.sh
```

---

## Benefits

| Aspect | Before | After |
|--------|--------|-------|
| **Navigation** | 14 files in root | Grouped by function |
| **Imports** | `from context_analyzer import ...` | `from src.analysis.context_analyzer import ...` |
| **Scalability** | Hard to add features | Easy to add modules |
| **Testing** | All tests in one folder | Organized by type (unit/integration) |
| **Documentation** | Scattered .md files | All in docs/ |
| **Maintenance** | Hard to find related code | Related code together |

---

## Migration Steps

### Phase 1: Create Directory Structure

```bash
mkdir -p src/{core,data,levels,analysis,trading,reporting,utils}
mkdir -p tests/{unit,integration,fixtures,data}
mkdir -p docs
mkdir -p output/{csv,backups}
mkdir -p scripts
```

### Phase 2: Move Files

**Move to src/core/**
```
agent.py → src/core/agent.py
(create src/core/run.py as entry point)
```

**Move to src/data/**
```
config.py → src/data/config.py
data_fetcher.py → src/data/data_fetcher.py
spy_fetcher.py → src/data/spy_fetcher.py
```

**Move to src/levels/**
```
daily_levels.py → src/levels/daily_levels.py
levels_analyzer.py → src/levels/levels_analyzer.py
spy_levels_analyzer.py → src/levels/spy_levels_analyzer.py
```

**Move to src/analysis/**
```
context_analyzer.py → src/analysis/context_analyzer.py
probability_engine.py → src/analysis/probability_engine.py
```

**Move to src/trading/**
```
trade_journal.py → src/trading/trade_journal.py
fill_trade.py → src/trading/fill_trade.py (as module, not CLI)
```

**Move to src/reporting/**
```
daily_report.py → src/reporting/daily_report.py
discord_formatter.py → src/reporting/discord_formatter.py
report_scheduler.py → src/reporting/report_scheduler.py
```

**Move to docs/**
```
*.md files → docs/
```

**Move to tests/**
```
tests/test_*.py → tests/unit/
tests/fixtures.py → tests/fixtures/
```

### Phase 3: Update Imports

Before:
```python
from config import ALERT_COOLDOWN_SECS
from data_fetcher import MultiTimeframeFetcher
from context_analyzer import build_mtf_context
```

After:
```python
from src.data.config import ALERT_COOLDOWN_SECS
from src.data.data_fetcher import MultiTimeframeFetcher
from src.analysis.context_analyzer import build_mtf_context
```

### Phase 4: Create __init__.py Files

Each module needs `__init__.py` for proper imports.

### Phase 5: Create Entry Point

```python
# src/core/run.py
if __name__ == "__main__":
    from src.core.agent import main
    main()
```

Then run as: `python -m src.core.run` or `python src/core/run.py`

---

## New Entry Points

### Run Agent
```bash
python src/core/run.py
# or
python -m src.core.agent
```

### Record Trade
```bash
python -m src.trading.fill_trade --alert-id=1 --exit-price=30450.50
```

### Generate Report
```bash
python -m src.reporting.daily_report --date="2026-06-05"
```

### Run Tests
```bash
pytest tests/unit/
pytest tests/integration/
pytest tests/
```

---

## Import Strategy

### Option A: Short Imports (Recommended)

Expose key classes in module `__init__.py`:

```python
# src/data/__init__.py
from .config import ALERT_COOLDOWN_SECS, TIMEZONE
from .data_fetcher import MultiTimeframeFetcher
from .spy_fetcher import SpyFetcher

# src/analysis/__init__.py
from .context_analyzer import build_mtf_context
from .probability_engine import get_probability

# Usage:
from src.data import MultiTimeframeFetcher, SpyFetcher
from src.analysis import build_mtf_context, get_probability
```

### Option B: Full Path Imports

```python
# Usage:
from src.data.data_fetcher import MultiTimeframeFetcher
from src.analysis.context_analyzer import build_mtf_context
```

**Recommendation:** Use Option A (shorter, cleaner)

---

## Gitignore Updates

```
# .gitignore
__pycache__/
*.pyc
.pytest_cache/
.env
*.db
reports/
output/csv/
output/backups/
.DS_Store
*.log
```

---

## Testing Changes

Current:
```bash
pytest tests/
```

After restructure:
```bash
# Run all tests
pytest tests/

# Run unit tests only
pytest tests/unit/

# Run integration tests
pytest tests/integration/

# Run specific test file
pytest tests/unit/test_context_analyzer.py

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

---

## Configuration Management

### Before
- `config.py` in root (import from anywhere)

### After
- `src/data/config.py` (centralized)
- Can import from any module: `from src.data import ALERT_COOLDOWN_SECS`
- Load from `.env` automatically on startup

---

## Benefits for Future

### Adding New Features
```
Want to add a new data source?
  → Create src/data/new_source.py

Want to add new analysis?
  → Create src/analysis/new_analysis.py

Want to add new reporting format?
  → Create src/reporting/new_format.py
```

### Scaling
- Easy to split into multiple developers
- Each person can work on a module independently
- Clear separation of concerns

### Maintenance
- Finding related code is easy
- Dependencies are clear
- Refactoring is safer

---

## Implementation Effort

- **Manual move:** ~20 minutes (drag-drop in file explorer)
- **Update imports:** ~30 minutes (find/replace)
- **Test/verify:** ~20 minutes (run tests, smoke test)
- **Total:** ~1 hour

---

## Rollback Plan

If something breaks:
1. Git has your original code
2. Can revert with: `git checkout HEAD~1`
3. Or rename folders back and revert imports

---

## Next Steps

1. **Confirm you want this restructure** (Yes/No)
2. If yes, I can:
   - Create all directories automatically
   - Move files (using git mv to preserve history)
   - Update all imports
   - Test everything
   - Verify it works

---

Would you like me to proceed with the restructuring?

The benefits:
- ✅ Much cleaner organization
- ✅ Easier to navigate
- ✅ Easier to scale
- ✅ Better for team collaboration
- ✅ Professional project structure

And it's **completely reversible** if needed!
