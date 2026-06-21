# Testing Guide — MNQ Agent v3

**Version:** 1.0  
**Status:** Active  
**Last Updated:** 2026-06-20

---

## Quick Start — Run All Tests

```bash
# Install pytest (if not already installed)
pip install pytest

# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src
```

---

## Test Structure

```
tests/
├── unit/
│   ├── test_vwap_analyzer.py       (NEW - VWAP bounce detection)
│   ├── test_ma_analyzer.py          (NEW - MA alignment checking)
│   ├── test_volume_analyzer.py      (NEW - Volume & POC analysis)
│   ├── test_context_analyzer.py     (OLD - Deprecated)
│   ├── test_data_fetcher.py         (OLD - Deprecated)
│   ├── test_discord_formatter.py    (Keep - Still relevant)
│   ├── test_probability_engine.py   (Keep - Still relevant)
│   ├── test_levels_analyzer.py      (OLD - Deprecated)
│   └── test_trade_journal.py        (Keep - Still relevant)
└── integration/
    └── (None yet - could add full system tests)
```

---

## NEW TESTS — Run These

### Test VWAP Analyzer (5m Bounce Detection)

```bash
pytest tests/unit/test_vwap_analyzer.py -v
```

**What it tests:**
- VWAP calculation from bars
- LONG bounce detection
- SHORT bounce detection
- VWAP support/resistance classification

**Expected output:**
```
test_vwap_analyzer.py::TestCalculateVWAP::test_vwap_simple PASSED
test_vwap_analyzer.py::TestCalculateVWAP::test_vwap_insufficient_data PASSED
test_vwap_analyzer.py::TestDetectVWAPBounce::test_long_bounce_detected PASSED
test_vwap_analyzer.py::TestDetectVWAPBounce::test_short_bounce_detected PASSED
test_vwap_analyzer.py::TestVWAPSupportResistance::test_support_classification PASSED
...
```

### Test MA Analyzer (15m + 1d Alignment)

```bash
pytest tests/unit/test_ma_analyzer.py -v
```

**What it tests:**
- SMA calculation (5, 20, 50 periods)
- MA alignment checking (bullish, bearish, none)
- MA level classification (support, resistance)
- Trend strength detection

**Expected output:**
```
test_ma_analyzer.py::TestCalculateSMA::test_sma_5_period PASSED
test_ma_analyzer.py::TestCheckMAAlignment::test_bullish_alignment PASSED
test_ma_analyzer.py::TestCheckMAAlignment::test_bearish_alignment PASSED
test_ma_analyzer.py::TestClassifyMALevels::test_support_levels PASSED
...
```

### Test Volume Analyzer (Spikes & POC)

```bash
pytest tests/unit/test_volume_analyzer.py -v
```

**What it tests:**
- POC (Point of Control) calculation
- Volume spike detection
- Volume confirmation for entry direction
- Confidence scoring

**Expected output:**
```
test_volume_analyzer.py::TestCalculatePOC::test_poc_simple PASSED
test_volume_analyzer.py::TestDetectVolumeSpike::test_volume_spike_detected PASSED
test_volume_analyzer.py::TestVolumeConfirmation::test_long_volume_confirms PASSED
...
```

---

## Run Specific Test Classes

### Run only VWAP bounce tests

```bash
pytest tests/unit/test_vwap_analyzer.py::TestDetectVWAPBounce -v
```

### Run only MA alignment tests

```bash
pytest tests/unit/test_ma_analyzer.py::TestCheckMAAlignment -v
```

### Run only volume spike tests

```bash
pytest tests/unit/test_volume_analyzer.py::TestDetectVolumeSpike -v
```

---

## Run Specific Test Cases

### Test single function

```bash
# Test LONG bounce detection only
pytest tests/unit/test_vwap_analyzer.py::TestDetectVWAPBounce::test_long_bounce_detected -v

# Test bullish alignment only
pytest tests/unit/test_ma_analyzer.py::TestCheckMAAlignment::test_bullish_alignment -v

# Test POC calculation only
pytest tests/unit/test_volume_analyzer.py::TestCalculatePOC::test_poc_simple -v
```

---

## Test Coverage Report

```bash
# Run tests with coverage
pytest tests/ --cov=src --cov-report=html

# View coverage report
open htmlcov/index.html  # macOS
start htmlcov/index.html # Windows
# Or open manually: htmlcov/index.html
```

---

## Integration Testing

### Manual Test: Full Alert Flow

```bash
# 1. Start agent in Terminal 1
python src/core/run.py

# 2. Monitor logs in Terminal 2
tail -f agent.log | grep -i "confluence\|bounce\|alert"

# 3. Verify alerts are generated with correct structure
sqlite3 trades.db "SELECT id, direction, confluence_score, probability FROM alerts ORDER BY timestamp DESC LIMIT 1;"
```

### Manual Test: Exit Tracking

```bash
# 1. Start monitor in Terminal 3
python src/monitoring/monitor.py --discord-off

# 2. Monitor logs
tail -f monitor.log | grep -i "hit\|exit\|recorded"

# 3. Verify exits are recorded
sqlite3 trades.db "SELECT id, alert_id, result, pnl FROM trades ORDER BY timestamp DESC LIMIT 1;"
```

---

## Common Test Scenarios

### Scenario 1: High Confluence Score Alert

**Expected behavior:**
- VWAP bounce detected
- MA5 > MA20 > MA50 (bullish)
- Volume spike confirmed
- POC proximity ✓
- Score: 8-10 points
- Alert generated

**Test:**
```bash
pytest tests/unit/test_vwap_analyzer.py::TestDetectVWAPBounce::test_long_bounce_detected -v
pytest tests/unit/test_ma_analyzer.py::TestCheckMAAlignment::test_bullish_alignment -v
pytest tests/unit/test_volume_analyzer.py::TestDetectVolumeSpike::test_volume_spike_detected -v
```

### Scenario 2: Low Confluence Score (No Alert)

**Expected behavior:**
- VWAP bounce detected
- MA5 < MA20 (not aligned)
- No volume spike
- Score: <6 points
- Alert filtered

**Test:**
```bash
pytest tests/unit/test_ma_analyzer.py::TestCheckMAAlignment::test_mixed_no_alignment -v
pytest tests/unit/test_volume_analyzer.py::TestDetectVolumeSpike::test_no_volume_spike -v
```

### Scenario 3: Volume Not Confirming

**Expected behavior:**
- VWAP bounce detected
- MA aligned
- Volume below average
- Confidence reduced
- May still alert if confluence ≥6

**Test:**
```bash
pytest tests/unit/test_volume_analyzer.py::TestVolumeConfirmation::test_volume_not_confirming -v
```

---

## Debugging Tests

### Run with detailed output

```bash
pytest tests/unit/test_vwap_analyzer.py -vv --tb=short
```

### Run with print statements

```bash
pytest tests/unit/test_vwap_analyzer.py -v -s
```

### Run failing tests only

```bash
pytest tests/ --lf  # Last failed
pytest tests/ -x    # Stop on first failure
```

---

## Old Tests (Deprecated)

These tests are for the old sweep-based system and may fail:

```bash
pytest tests/unit/test_context_analyzer.py     # OLD - Sweep detection
pytest tests/unit/test_levels_analyzer.py      # OLD - Pivot logic
pytest tests/unit/test_data_fetcher.py         # OLD - May have API changes
```

**Note:** These can be kept for reference but are not required for v3.

---

## Test Requirements

```bash
# Install dependencies
pip install pytest
pip install pytest-cov

# Optional: parallel testing
pip install pytest-xdist
pytest tests/ -n auto  # Run tests in parallel
```

---

## Continuous Integration

### Run tests before committing

```bash
# Run all new tests
pytest tests/unit/test_vwap_analyzer.py \
       tests/unit/test_ma_analyzer.py \
       tests/unit/test_volume_analyzer.py -v
```

### Generate report

```bash
pytest tests/ --cov=src --cov-report=term-missing
```

---

## Performance Benchmarks

### Test Execution Time

Expected:
- Individual test: <100ms
- Full suite (3 modules): <1s
- With coverage: <3s

```bash
# Time tests
time pytest tests/unit/test_vwap_analyzer.py
```

---

## Next Steps

### 1. Run New Tests First

```bash
pytest tests/unit/test_vwap_analyzer.py \
       tests/unit/test_ma_analyzer.py \
       tests/unit/test_volume_analyzer.py -v
```

### 2. Verify All Pass

Expected: 30+ tests pass

### 3. Check Coverage

```bash
pytest tests/ --cov=src --cov-report=term-missing
```

Expected: 80%+ coverage on new modules

### 4. Add More Tests (Optional)

Create `tests/integration/test_full_alert_flow.py` for end-to-end testing

---

## Reference

| Command | Purpose |
|---------|---------|
| `pytest tests/` | Run all tests |
| `pytest tests/ -v` | Verbose output |
| `pytest tests/ --cov=src` | With coverage |
| `pytest tests/unit/test_vwap_analyzer.py` | Run one module |
| `pytest tests/ -k bounce` | Run tests matching "bounce" |
| `pytest tests/ --lf` | Last failed only |
| `pytest tests/ -x` | Stop on first failure |

---

**Status:** Ready to Test  
**Coverage Target:** 80%+  
**Test Count:** 30+ unit tests (new), TBD integration tests
