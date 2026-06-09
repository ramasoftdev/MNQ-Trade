"""
Unit tests for trade_journal.py
Tests database operations, alert logging, and statistics calculation.
"""

import pytest
import os
from datetime import datetime, timedelta
import tempfile

from src.trading.trade_journal import TradeJournal


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def journal(temp_db):
    """Create a TradeJournal instance with temp database."""
    return TradeJournal(temp_db)


class TestAlertLogging:
    """Test alert logging functionality."""

    def test_log_alert_returns_id(self, journal):
        """Logging an alert should return an ID."""
        alert_data = {
            "timestamp": datetime.now(),
            "direction": "LONG",
            "current_price": 30450.50,
            "trigger_tf": "5m",
            "confluence_score": 8.5,
        }
        alert_id = journal.log_alert(alert_data)
        assert alert_id > 0

    def test_get_alert(self, journal):
        """Should retrieve logged alert by ID."""
        alert_data = {
            "timestamp": datetime.now(),
            "direction": "SHORT",
            "current_price": 30420.25,
            "trigger_tf": "15m",
            "confluence_score": 9.0,
            "probability": 75,
            "assessment": "TAKE",
        }
        alert_id = journal.log_alert(alert_data)
        alert = journal.get_alert(alert_id)

        assert alert is not None
        assert alert["direction"] == "SHORT"
        assert alert["entry_price"] == 30420.25  # Stored as entry_price
        assert alert["probability"] == 75
        assert alert["assessment"] == "TAKE"

    def test_alerts_by_date(self, journal):
        """Should retrieve all alerts for a date."""
        today = datetime.now().strftime("%Y-%m-%d")

        # Log 3 alerts
        for i in range(3):
            journal.log_alert({
                "timestamp": datetime.now(),
                "direction": "LONG" if i % 2 == 0 else "SHORT",
                "current_price": 30450.0 + i,
                "confluence_score": 8.0 + i,
            })

        alerts = journal.get_alerts_by_date(today)
        assert len(alerts) == 3


class TestTradeRecording:
    """Test trade fill recording."""

    def test_record_fill_long_trade(self, journal):
        """Recording a winning LONG trade should calculate correct P&L."""
        # Log alert
        alert_data = {
            "timestamp": datetime.now(),
            "direction": "LONG",
            "current_price": 30450.00,
        }
        alert_id = journal.log_alert(alert_data)

        # Record fill (exited at 30460)
        exit_time = datetime.now() + timedelta(minutes=30)
        journal.record_fill(alert_id, exit_price=30460.00, exit_time=exit_time)

        # Verify trade
        trade = journal.get_trade(alert_id)
        assert trade is not None
        assert trade["entry_price"] == 30450.00
        assert trade["exit_price"] == 30460.00
        assert trade["pnl"] == (30460.00 - 30450.00) * 20  # $200
        assert trade["result"] == "WIN"

    def test_record_fill_short_trade(self, journal):
        """Recording a winning SHORT trade should calculate correct P&L."""
        alert_data = {
            "timestamp": datetime.now(),
            "direction": "SHORT",
            "current_price": 30450.00,
        }
        alert_id = journal.log_alert(alert_data)

        # Record fill (exited at 30440, profit)
        exit_time = datetime.now() + timedelta(minutes=20)
        journal.record_fill(alert_id, exit_price=30440.00, exit_time=exit_time)

        trade = journal.get_trade(alert_id)
        assert trade is not None
        assert trade["pnl"] == (30450.00 - 30440.00) * 20  # $200
        assert trade["result"] == "WIN"

    def test_record_fill_loss(self, journal):
        """Recording a losing trade should mark as LOSS."""
        alert_data = {
            "timestamp": datetime.now(),
            "direction": "LONG",
            "current_price": 30450.00,
        }
        alert_id = journal.log_alert(alert_data)

        # Exit at loss
        journal.record_fill(alert_id, exit_price=30440.00)

        trade = journal.get_trade(alert_id)
        assert trade["pnl"] < 0
        assert trade["result"] == "LOSS"

    def test_alert_status_updated_on_fill(self, journal):
        """Alert status should change to FILLED when trade is recorded."""
        alert_id = journal.log_alert({
            "timestamp": datetime.now(),
            "direction": "LONG",
            "current_price": 30450.00,
        })

        alert = journal.get_alert(alert_id)
        assert alert["trade_status"] == "PENDING"

        journal.record_fill(alert_id, 30460.00)

        alert = journal.get_alert(alert_id)
        assert alert["trade_status"] == "FILLED"


class TestStatistics:
    """Test statistics calculation."""

    def test_daily_stats_empty_day(self, journal):
        """Stats for a day with no alerts should be zeros."""
        stats = journal.get_daily_stats("2020-01-01")
        assert stats["total_alerts"] == 0
        assert stats["total_trades"] == 0
        assert stats["win_rate_pct"] == 0

    def test_daily_stats_with_trades(self, journal):
        """Stats should aggregate win/loss correctly."""
        today = datetime.now().strftime("%Y-%m-%d")

        # Log 4 alerts
        alert_ids = []
        for i in range(4):
            alert_id = journal.log_alert({
                "timestamp": datetime.now(),
                "direction": "LONG" if i % 2 == 0 else "SHORT",
                "current_price": 30450.00,
                "confluence_score": 8.0,
            })
            alert_ids.append(alert_id)

        # Fill 2 as wins, 1 as loss, 1 as pending
        journal.record_fill(alert_ids[0], 30460.00)  # LONG WIN +$200
        journal.record_fill(alert_ids[1], 30460.00)  # SHORT LOSS -$200 (short at 30450, exit at 30460)
        journal.record_fill(alert_ids[2], 30455.00)  # LONG WIN +$100
        # alert_ids[3] left pending

        stats = journal.get_daily_stats(today)
        assert stats["total_alerts"] == 4
        assert stats["total_trades"] == 3
        assert stats["trades_won"] == 2
        assert stats["trades_lost"] == 1
        assert stats["win_rate_pct"] == pytest.approx(66.7, abs=0.1)
        assert stats["total_pnl"] == 100.0  # 200 - 200 + 100

    def test_setup_stats_by_direction(self, journal):
        """Setup stats should break down by LONG/SHORT."""
        today = datetime.now().strftime("%Y-%m-%d")

        # 2 LONG trades (both wins)
        for i in range(2):
            alert_id = journal.log_alert({
                "timestamp": datetime.now(),
                "direction": "LONG",
                "current_price": 30450.00,
            })
            journal.record_fill(alert_id, 30460.00)

        # 2 SHORT trades (1 win, 1 loss)
        short_alert_1 = journal.log_alert({
            "timestamp": datetime.now(),
            "direction": "SHORT",
            "current_price": 30450.00,
        })
        journal.record_fill(short_alert_1, 30440.00)  # WIN

        short_alert_2 = journal.log_alert({
            "timestamp": datetime.now(),
            "direction": "SHORT",
            "current_price": 30450.00,
        })
        journal.record_fill(short_alert_2, 30460.00)  # LOSS

        stats = journal.get_setup_stats(today)

        assert stats["by_direction"]["LONG"]["total"] == 2
        assert stats["by_direction"]["LONG"]["won"] == 2
        assert stats["by_direction"]["LONG"]["win_rate"] == 100.0

        assert stats["by_direction"]["SHORT"]["total"] == 2
        assert stats["by_direction"]["SHORT"]["won"] == 1
        assert stats["by_direction"]["SHORT"]["win_rate"] == 50.0

    def test_date_range_stats(self, journal):
        """Should aggregate stats across multiple dates."""
        # Log trades on two consecutive days
        for day_offset in [0, 1]:
            ts = datetime.now() + timedelta(days=day_offset)
            alert_id = journal.log_alert({
                "timestamp": ts,
                "direction": "LONG",
                "current_price": 30450.00,
            })
            journal.record_fill(alert_id, 30460.00)

        start = (datetime.now()).strftime("%Y-%m-%d")
        end = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        stats = journal.get_date_range_stats(start, end)
        assert stats["total_trades"] == 2
        assert stats["trades_won"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
