"""
Cost Tracker Service - Redis-based API cost tracking and analytics.

This service tracks API usage, costs, and provides analytics for monitoring
and optimization of Gemini API calls.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import redis
from redis.exceptions import RedisError


logger = logging.getLogger(__name__)


class CostTracker:
    """
    Tracks API costs and usage metrics using Redis.

    Stores daily aggregated data with automatic 30-day retention.
    """

    # Redis key prefixes
    KEY_PREFIX_DAILY = "cost:daily:"
    KEY_PREFIX_CALL = "cost:call:"

    # Data retention in seconds (30 days)
    RETENTION_SECONDS = 30 * 24 * 60 * 60

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """
        Initialize the cost tracker.

        Args:
            redis_url: Redis connection URL

        Raises:
            RedisError: If connection to Redis fails
        """
        try:
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"CostTracker initialized with Redis at {redis_url}")
        except RedisError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    def track_api_call(
        self,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        thinking_tokens: int,
        cost: float,
        operation_type: str,
        contract_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Track an API call with cost and usage information.

        Args:
            model_name: Name of the Gemini model used
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            thinking_tokens: Number of thinking tokens (for reasoning models)
            cost: Cost of the call in USD
            operation_type: Type of operation (e.g., 'parse', 'analyze', 'query')
            contract_id: Optional contract identifier
            metadata: Optional additional metadata

        Raises:
            RedisError: If tracking fails
        """
        try:
            timestamp = datetime.utcnow()
            date_key = timestamp.strftime("%Y-%m-%d")

            # Store individual call data (with shorter retention for debugging)
            call_id = f"{date_key}:{timestamp.timestamp()}"
            call_key = f"{self.KEY_PREFIX_CALL}{call_id}"

            call_data = {
                "model_name": model_name,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "thinking_tokens": thinking_tokens,
                "total_tokens": input_tokens + output_tokens + thinking_tokens,
                "cost": cost,
                "operation_type": operation_type,
                "contract_id": contract_id,
                "timestamp": timestamp.isoformat(),
                "metadata": json.dumps(metadata) if metadata else None,
            }

            # Store call data with 7-day retention (for detailed analysis)
            self.redis_client.hset(call_key, mapping=call_data)
            self.redis_client.expire(call_key, 7 * 24 * 60 * 60)

            # Update daily aggregates
            self._update_daily_aggregates(
                date_key=date_key,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=thinking_tokens,
                cost=cost,
                operation_type=operation_type,
            )

            logger.debug(
                f"Tracked API call: {model_name} - {operation_type} - "
                f"{input_tokens + output_tokens + thinking_tokens} tokens - ${cost:.6f}"
            )

        except RedisError as e:
            logger.error(f"Failed to track API call: {e}")
            raise

    def _update_daily_aggregates(
        self,
        date_key: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        thinking_tokens: int,
        cost: float,
        operation_type: str,
    ) -> None:
        """
        Update daily aggregate statistics.

        Args:
            date_key: Date in YYYY-MM-DD format
            model_name: Name of the Gemini model
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            thinking_tokens: Number of thinking tokens
            cost: Cost in USD
            operation_type: Type of operation
        """
        daily_key = f"{self.KEY_PREFIX_DAILY}{date_key}"

        # Increment counters atomically
        pipe = self.redis_client.pipeline()

        # Overall totals
        pipe.hincrby(daily_key, "total_calls", 1)
        pipe.hincrbyfloat(daily_key, "total_cost", cost)
        pipe.hincrby(daily_key, "total_tokens", input_tokens + output_tokens + thinking_tokens)
        pipe.hincrby(daily_key, "input_tokens", input_tokens)
        pipe.hincrby(daily_key, "output_tokens", output_tokens)
        pipe.hincrby(daily_key, "thinking_tokens", thinking_tokens)

        # Model-specific totals
        pipe.hincrby(daily_key, f"model:{model_name}:calls", 1)
        pipe.hincrbyfloat(daily_key, f"model:{model_name}:cost", cost)
        pipe.hincrby(daily_key, f"model:{model_name}:tokens", input_tokens + output_tokens + thinking_tokens)
        pipe.hincrby(daily_key, f"model:{model_name}:input_tokens", input_tokens)
        pipe.hincrby(daily_key, f"model:{model_name}:output_tokens", output_tokens)
        pipe.hincrby(daily_key, f"model:{model_name}:thinking_tokens", thinking_tokens)

        # Operation-specific totals
        pipe.hincrby(daily_key, f"operation:{operation_type}:calls", 1)
        pipe.hincrbyfloat(daily_key, f"operation:{operation_type}:cost", cost)

        # Set expiration (30 days)
        pipe.expire(daily_key, self.RETENTION_SECONDS)

        pipe.execute()

    def get_daily_costs(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get cost summary for a specific date.

        Args:
            date: Date to get costs for (defaults to today)

        Returns:
            Dictionary with cost breakdown and statistics

        Raises:
            RedisError: If retrieval fails
        """
        if date is None:
            date = datetime.utcnow()

        date_key = date.strftime("%Y-%m-%d")
        daily_key = f"{self.KEY_PREFIX_DAILY}{date_key}"

        try:
            data = self.redis_client.hgetall(daily_key)

            if not data:
                return {
                    "date": date_key,
                    "total_cost": 0.0,
                    "total_tokens": 0,
                    "total_calls": 0,
                    "by_model": [],
                    "by_operation": {},
                }

            # Parse overall totals
            total_cost = float(data.get("total_cost", 0))
            total_tokens = int(data.get("total_tokens", 0))
            total_calls = int(data.get("total_calls", 0))
            input_tokens = int(data.get("input_tokens", 0))
            output_tokens = int(data.get("output_tokens", 0))
            thinking_tokens = int(data.get("thinking_tokens", 0))

            # Parse model breakdown
            models = {}
            operations = {}

            for key, value in data.items():
                if key.startswith("model:"):
                    parts = key.split(":")
                    if len(parts) >= 3:
                        model_name = parts[1]
                        metric = parts[2]

                        if model_name not in models:
                            models[model_name] = {
                                "model_name": model_name,
                                "calls": 0,
                                "cost": 0.0,
                                "tokens": 0,
                                "input_tokens": 0,
                                "output_tokens": 0,
                                "thinking_tokens": 0,
                            }

                        if metric == "calls":
                            models[model_name]["calls"] = int(value)
                        elif metric == "cost":
                            models[model_name]["cost"] = float(value)
                        elif metric == "tokens":
                            models[model_name]["tokens"] = int(value)
                        elif metric == "input_tokens":
                            models[model_name]["input_tokens"] = int(value)
                        elif metric == "output_tokens":
                            models[model_name]["output_tokens"] = int(value)
                        elif metric == "thinking_tokens":
                            models[model_name]["thinking_tokens"] = int(value)

                elif key.startswith("operation:"):
                    parts = key.split(":")
                    if len(parts) >= 3:
                        operation = parts[1]
                        metric = parts[2]

                        if operation not in operations:
                            operations[operation] = {"calls": 0, "cost": 0.0}

                        if metric == "calls":
                            operations[operation]["calls"] = int(value)
                        elif metric == "cost":
                            operations[operation]["cost"] = float(value)

            return {
                "date": date_key,
                "total_cost": total_cost,
                "total_tokens": total_tokens,
                "total_calls": total_calls,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "thinking_tokens": thinking_tokens,
                "by_model": list(models.values()),
                "by_operation": operations,
            }

        except RedisError as e:
            logger.error(f"Failed to get daily costs: {e}")
            raise

    def get_date_range_costs(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get cost data for a range of dates.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive, defaults to today)

        Returns:
            List of daily cost summaries

        Raises:
            RedisError: If retrieval fails
        """
        if end_date is None:
            end_date = datetime.utcnow()

        results = []
        current_date = start_date

        while current_date <= end_date:
            daily_costs = self.get_daily_costs(current_date)
            results.append(daily_costs)
            current_date += timedelta(days=1)

        return results

    def get_total_costs(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get aggregated costs for a date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive, defaults to today)

        Returns:
            Aggregated cost summary

        Raises:
            RedisError: If retrieval fails
        """
        daily_data = self.get_date_range_costs(start_date, end_date)

        total_cost = sum(day["total_cost"] for day in daily_data)
        total_tokens = sum(day["total_tokens"] for day in daily_data)
        total_calls = sum(day["total_calls"] for day in daily_data)

        # Aggregate by model
        model_totals = {}
        for day in daily_data:
            for model in day["by_model"]:
                model_name = model["model_name"]
                if model_name not in model_totals:
                    model_totals[model_name] = {
                        "model_name": model_name,
                        "calls": 0,
                        "cost": 0.0,
                        "tokens": 0,
                    }
                model_totals[model_name]["calls"] += model["calls"]
                model_totals[model_name]["cost"] += model["cost"]
                model_totals[model_name]["tokens"] += model["tokens"]

        # Aggregate by operation
        operation_totals = {}
        for day in daily_data:
            for op_name, op_data in day["by_operation"].items():
                if op_name not in operation_totals:
                    operation_totals[op_name] = {"calls": 0, "cost": 0.0}
                operation_totals[op_name]["calls"] += op_data["calls"]
                operation_totals[op_name]["cost"] += op_data["cost"]

        return {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": (end_date or datetime.utcnow()).strftime("%Y-%m-%d"),
            "total_cost": total_cost,
            "total_tokens": total_tokens,
            "total_calls": total_calls,
            "by_model": list(model_totals.values()),
            "by_operation": operation_totals,
            "daily_breakdown": daily_data,
        }

    def clear_date(self, date: datetime) -> None:
        """
        Clear cost data for a specific date.

        Args:
            date: Date to clear

        Raises:
            RedisError: If deletion fails
        """
        date_key = date.strftime("%Y-%m-%d")
        daily_key = f"{self.KEY_PREFIX_DAILY}{date_key}"

        try:
            self.redis_client.delete(daily_key)
            logger.info(f"Cleared cost data for {date_key}")
        except RedisError as e:
            logger.error(f"Failed to clear cost data: {e}")
            raise

    def health_check(self) -> bool:
        """
        Check if Redis connection is healthy.

        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            self.redis_client.ping()
            return True
        except RedisError:
            return False
