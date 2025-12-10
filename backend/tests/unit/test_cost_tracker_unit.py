"""
Unit tests for CostTracker service.

Tests Redis operations, aggregation logic, and error handling without
requiring a live Redis instance.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from redis.exceptions import RedisError

from backend.services.cost_tracker import CostTracker


class TestCostTrackerUnit:
    """Unit tests for CostTracker class."""

    def test_initialization_with_redis_url(self, mock_redis):
        """Test that CostTracker initializes with Redis URL."""
        with patch('backend.services.cost_tracker.redis.from_url') as mock_from_url:
            mock_from_url.return_value = mock_redis

            tracker = CostTracker(redis_url="redis://localhost:6379")

            mock_from_url.assert_called_once()
            mock_redis.ping.assert_called_once()

    def test_initialization_fails_on_redis_connection_error(self):
        """Test that initialization raises RedisError if connection fails."""
        with patch('backend.services.cost_tracker.redis.from_url') as mock_from_url:
            mock_redis = MagicMock()
            mock_redis.ping.side_effect = RedisError("Connection refused")
            mock_from_url.return_value = mock_redis

            with pytest.raises(RedisError, match="Connection refused"):
                CostTracker(redis_url="redis://localhost:6379")

    def test_track_api_call_stores_call_data(self, mock_redis):
        """Test that API call data is stored in Redis."""
        with patch('backend.services.cost_tracker.redis.from_url', return_value=mock_redis):
            tracker = CostTracker(redis_url="redis://test")

            tracker.track_api_call(
                model_name="gemini-2.5-flash",
                input_tokens=100,
                output_tokens=50,
                thinking_tokens=0,
                cost=0.001,
                operation_type="risk_analysis",
                contract_id="test-123"
            )

            # Verify individual call was stored
            assert mock_redis.hset.called
            assert mock_redis.expire.called

    def test_track_api_call_updates_daily_aggregates(self, mock_redis):
        """Test that daily aggregates are updated correctly."""
        with patch('backend.services.cost_tracker.redis.from_url', return_value=mock_redis):
            tracker = CostTracker(redis_url="redis://test")

            tracker.track_api_call(
                model_name="gemini-2.5-flash",
                input_tokens=100,
                output_tokens=50,
                thinking_tokens=0,
                cost=0.001,
                operation_type="risk_analysis"
            )

            # Verify pipeline was used for atomic updates
            assert mock_redis.pipeline.called
            pipeline = mock_redis.pipeline.return_value
            assert pipeline.hincrby.called
            assert pipeline.hincrbyfloat.called
            assert pipeline.expire.called
            assert pipeline.execute.called

    def test_track_api_call_with_thinking_tokens(self, mock_redis):
        """Test tracking API calls with thinking tokens."""
        with patch('backend.services.cost_tracker.redis.from_url', return_value=mock_redis):
            tracker = CostTracker(redis_url="redis://test")

            tracker.track_api_call(
                model_name="gemini-3-pro",
                input_tokens=200,
                output_tokens=100,
                thinking_tokens=500,
                cost=0.005,
                operation_type="deep_analysis"
            )

            # Should include thinking tokens in total
            assert mock_redis.hset.called

    def test_track_api_call_with_metadata(self, mock_redis):
        """Test tracking API calls with custom metadata."""
        with patch('backend.services.cost_tracker.redis.from_url', return_value=mock_redis):
            tracker = CostTracker(redis_url="redis://test")

            metadata = {"user_id": "user-123", "session_id": "session-456"}

            tracker.track_api_call(
                model_name="gemini-2.5-flash",
                input_tokens=100,
                output_tokens=50,
                thinking_tokens=0,
                cost=0.001,
                operation_type="query",
                metadata=metadata
            )

            assert mock_redis.hset.called

    def test_get_daily_costs_returns_empty_for_no_data(self, mock_redis):
        """Test that get_daily_costs returns empty structure when no data exists."""
        mock_redis.hgetall.return_value = {}

        with patch('backend.services.cost_tracker.redis.from_url', return_value=mock_redis):
            tracker = CostTracker(redis_url="redis://test")

            result = tracker.get_daily_costs(datetime(2025, 1, 1))

            assert result["date"] == "2025-01-01"
            assert result["total_cost"] == 0.0
            assert result["total_tokens"] == 0
            assert result["total_calls"] == 0
            assert result["by_model"] == []
            assert result["by_operation"] == {}

    def test_get_daily_costs_aggregates_correctly(self, mock_redis):
        """Test daily cost aggregation with real data."""
        mock_redis.hgetall.return_value = {
            "total_cost": "0.005",
            "total_tokens": "1500",
            "total_calls": "5",
            "input_tokens": "1000",
            "output_tokens": "500",
            "thinking_tokens": "0",
            "model:gemini-2.5-flash:calls": "3",
            "model:gemini-2.5-flash:cost": "0.003",
            "model:gemini-2.5-flash:tokens": "900",
            "model:gemini-2.5-flash:input_tokens": "600",
            "model:gemini-2.5-flash:output_tokens": "300",
            "model:gemini-2.5-flash:thinking_tokens": "0",
            "model:gemini-2.5-pro:calls": "2",
            "model:gemini-2.5-pro:cost": "0.002",
            "model:gemini-2.5-pro:tokens": "600",
            "model:gemini-2.5-pro:input_tokens": "400",
            "model:gemini-2.5-pro:output_tokens": "200",
            "model:gemini-2.5-pro:thinking_tokens": "0",
            "operation:risk_analysis:calls": "3",
            "operation:risk_analysis:cost": "0.003",
            "operation:query:calls": "2",
            "operation:query:cost": "0.002"
        }

        with patch('backend.services.cost_tracker.redis.from_url', return_value=mock_redis):
            tracker = CostTracker(redis_url="redis://test")

            result = tracker.get_daily_costs(datetime(2025, 1, 1))

            assert result["total_cost"] == 0.005
            assert result["total_tokens"] == 1500
            assert result["total_calls"] == 5
            assert len(result["by_model"]) == 2
            assert len(result["by_operation"]) == 2

            # Check model breakdown
            flash_model = next(m for m in result["by_model"] if m["model_name"] == "gemini-2.5-flash")
            assert flash_model["calls"] == 3
            assert flash_model["cost"] == 0.003
            assert flash_model["tokens"] == 900

            # Check operation breakdown
            assert result["by_operation"]["risk_analysis"]["calls"] == 3
            assert result["by_operation"]["risk_analysis"]["cost"] == 0.003

    def test_get_daily_costs_defaults_to_today(self, mock_redis):
        """Test that get_daily_costs defaults to today's date."""
        mock_redis.hgetall.return_value = {}

        with patch('backend.services.cost_tracker.redis.from_url', return_value=mock_redis):
            tracker = CostTracker(redis_url="redis://test")

            result = tracker.get_daily_costs()

            today = datetime.utcnow().strftime("%Y-%m-%d")
            assert result["date"] == today

    def test_get_date_range_costs(self, mock_redis):
        """Test getting costs for a date range."""
        mock_redis.hgetall.return_value = {
            "total_cost": "0.001",
            "total_tokens": "100",
            "total_calls": "1",
            "input_tokens": "60",
            "output_tokens": "40",
            "thinking_tokens": "0"
        }

        with patch('backend.services.cost_tracker.redis.from_url', return_value=mock_redis):
            tracker = CostTracker(redis_url="redis://test")

            start_date = datetime(2025, 1, 1)
            end_date = datetime(2025, 1, 3)

            results = tracker.get_date_range_costs(start_date, end_date)

            # Should return 3 days of data
            assert len(results) == 3
            assert all("date" in r for r in results)

    def test_get_total_costs_aggregates_multiple_days(self, mock_redis):
        """Test aggregating costs across multiple days."""
        # Mock different data for each day
        call_count = [0]

        def mock_hgetall(key):
            call_count[0] += 1
            if call_count[0] == 1:
                return {
                    "total_cost": "0.001",
                    "total_tokens": "100",
                    "total_calls": "1",
                    "input_tokens": "60",
                    "output_tokens": "40",
                    "thinking_tokens": "0"
                }
            else:
                return {
                    "total_cost": "0.002",
                    "total_tokens": "200",
                    "total_calls": "2",
                    "input_tokens": "120",
                    "output_tokens": "80",
                    "thinking_tokens": "0"
                }

        mock_redis.hgetall = MagicMock(side_effect=mock_hgetall)

        with patch('backend.services.cost_tracker.redis.from_url', return_value=mock_redis):
            tracker = CostTracker(redis_url="redis://test")

            start_date = datetime(2025, 1, 1)
            end_date = datetime(2025, 1, 2)

            result = tracker.get_total_costs(start_date, end_date)

            assert result["total_cost"] == 0.003
            assert result["total_tokens"] == 300
            assert result["total_calls"] == 3

    def test_clear_date_deletes_redis_key(self, mock_redis):
        """Test that clear_date deletes the correct Redis key."""
        with patch('backend.services.cost_tracker.redis.from_url', return_value=mock_redis):
            tracker = CostTracker(redis_url="redis://test")

            date = datetime(2025, 1, 1)
            tracker.clear_date(date)

            mock_redis.delete.assert_called_once()
            call_args = mock_redis.delete.call_args[0][0]
            assert "2025-01-01" in call_args

    def test_health_check_returns_true_when_healthy(self, mock_redis):
        """Test that health_check returns True when Redis is healthy."""
        mock_redis.ping.return_value = True

        with patch('backend.services.cost_tracker.redis.from_url', return_value=mock_redis):
            tracker = CostTracker(redis_url="redis://test")

            assert tracker.health_check() is True

    def test_health_check_returns_false_when_unhealthy(self, mock_redis):
        """Test that health_check returns False when Redis is unhealthy."""
        mock_redis.ping.side_effect = RedisError("Connection lost")

        with patch('backend.services.cost_tracker.redis.from_url', return_value=mock_redis):
            # Need to bypass the initial ping in __init__
            with patch.object(mock_redis, 'ping', return_value=True):
                tracker = CostTracker(redis_url="redis://test")

            # Now set it to fail
            mock_redis.ping.side_effect = RedisError("Connection lost")

            assert tracker.health_check() is False

    def test_track_api_call_raises_on_redis_error(self, mock_redis):
        """Test that track_api_call raises RedisError on failure."""
        mock_redis.hset.side_effect = RedisError("Write failed")

        with patch('backend.services.cost_tracker.redis.from_url', return_value=mock_redis):
            tracker = CostTracker(redis_url="redis://test")

            with pytest.raises(RedisError):
                tracker.track_api_call(
                    model_name="gemini-2.5-flash",
                    input_tokens=100,
                    output_tokens=50,
                    thinking_tokens=0,
                    cost=0.001,
                    operation_type="test"
                )

    def test_retention_period_is_30_days(self):
        """Test that retention period constant is set to 30 days."""
        assert CostTracker.RETENTION_SECONDS == 30 * 24 * 60 * 60

    def test_key_prefixes_are_defined(self):
        """Test that Redis key prefixes are defined."""
        assert CostTracker.KEY_PREFIX_DAILY == "cost:daily:"
        assert CostTracker.KEY_PREFIX_CALL == "cost:call:"

    def test_get_daily_costs_handles_redis_error(self, mock_redis):
        """Test that get_daily_costs raises RedisError on failure."""
        mock_redis.hgetall.side_effect = RedisError("Read failed")

        with patch('backend.services.cost_tracker.redis.from_url', return_value=mock_redis):
            tracker = CostTracker(redis_url="redis://test")

            with pytest.raises(RedisError):
                tracker.get_daily_costs()

    def test_model_breakdown_with_multiple_metrics(self, mock_redis):
        """Test parsing model breakdown with all metrics."""
        mock_redis.hgetall.return_value = {
            "total_cost": "0.005",
            "total_tokens": "1500",
            "total_calls": "5",
            "input_tokens": "1000",
            "output_tokens": "400",
            "thinking_tokens": "100",
            "model:gemini-3-pro:calls": "2",
            "model:gemini-3-pro:cost": "0.005",
            "model:gemini-3-pro:tokens": "1500",
            "model:gemini-3-pro:input_tokens": "1000",
            "model:gemini-3-pro:output_tokens": "400",
            "model:gemini-3-pro:thinking_tokens": "100"
        }

        with patch('backend.services.cost_tracker.redis.from_url', return_value=mock_redis):
            tracker = CostTracker(redis_url="redis://test")

            result = tracker.get_daily_costs()

            assert len(result["by_model"]) == 1
            model = result["by_model"][0]
            assert model["thinking_tokens"] == 100
            assert model["input_tokens"] == 1000
            assert model["output_tokens"] == 400
