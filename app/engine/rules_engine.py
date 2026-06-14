"""
Rules Engine for Cortex Post
Evaluates conditions from rules against fetched provider data.
Supports operators: >, <, >=, <=, ==, !=, contains, not_contains, starts_with, between
Supports logic: AND (all conditions must be true), OR (any condition must be true)
"""
import json
import logging
from typing import Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class RulesEngine:
    """Evaluates rule conditions against provider data."""
    
    def evaluate(self, data: dict, conditions: list[dict], logic: str = "AND") -> bool:
        """
        Evaluate conditions against data.
        
        Args:
            data: Dictionary of field->value from provider (e.g., {"price": 50000, "coin": "BTC"})
            conditions: List of condition dicts: [{"field": "price", "operator": ">", "value": 50000}]
            logic: "AND" or "OR"
        
        Returns:
            bool: Whether the conditions are met
        """
        if not conditions:
            return True
        
        results = [self._evaluate_single(data, cond) for cond in conditions]
        
        if logic == "AND":
            return all(results)
        elif logic == "OR":
            return any(results)
        return False
    
    def _evaluate_single(self, data: dict, condition: dict) -> bool:
        """Evaluate a single condition."""
        field = condition.get("field", "")
        operator = condition.get("operator", "==")
        target_value = condition.get("value")
        
        actual_value = data.get(field)
        if actual_value is None:
            logger.warning(f"Field '{field}' not found in data")
            return False
        
        try:
            # Type coercion - try numeric comparison
            if operator in (">", "<", ">=", "<="):
                actual_value = float(actual_value)
                target_value = float(target_value)
        except (ValueError, TypeError):
            pass  # Keep as string comparison
        
        if operator == ">":
            return actual_value > target_value
        elif operator == "<":
            return actual_value < target_value
        elif operator == ">=":
            return actual_value >= target_value
        elif operator == "<=":
            return actual_value <= target_value
        elif operator == "==":
            return actual_value == target_value
        elif operator == "!=":
            return actual_value != target_value
        elif operator == "contains":
            return str(target_value).lower() in str(actual_value).lower()
        elif operator == "not_contains":
            return str(target_value).lower() not in str(actual_value).lower()
        elif operator == "starts_with":
            return str(actual_value).lower().startswith(str(target_value).lower())
        elif operator == "between":
            # value should be [min, max]
            if isinstance(target_value, (list, tuple)) and len(target_value) == 2:
                return float(target_value[0]) <= float(actual_value) <= float(target_value[1])
            return False
        else:
            logger.warning(f"Unknown operator: {operator}")
            return False
    
    def check_cooldown(self, last_triggered_at: str | None, cooldown_minutes: int) -> bool:
        """
        Check if rule is in cooldown period.
        Returns True if rule CAN fire (not in cooldown).
        """
        if not last_triggered_at:
            return True
        
        try:
            last = datetime.fromisoformat(last_triggered_at)
            next_fire = last + timedelta(minutes=cooldown_minutes)
            return datetime.utcnow() >= next_fire
        except (ValueError, TypeError):
            return True


rules_engine = RulesEngine()
