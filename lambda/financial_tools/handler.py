"""AWS Lambda entry point for deterministic, S3-backed financial calculations."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

try:
    from . import market_store, ops
    from .calculations import (
        analyze_holdings_exposure,
        compare_strategy_shift,
        market_snapshot,
        simulate_account_purchase,
    )
    from .data_access import load_dataset_from_s3
except ImportError:  # Lambda CodeUri places modules at the runtime root.
    import market_store
    import ops
    from calculations import (
        analyze_holdings_exposure,
        compare_strategy_shift,
        market_snapshot,
        simulate_account_purchase,
    )
    from data_access import load_dataset_from_s3


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    operation = event.get("operation")
    analysis_id = event.get("analysis_id", "unknown")
    request_id = getattr(context, "aws_request_id", "local")
    started_at = datetime.now(timezone.utc)
    logger.info(
        json.dumps(
            {
                "event": "calculation_started",
                "analysis_id": analysis_id,
                "operation": operation,
                "aws_request_id": request_id,
            }
        )
    )
    try:
        financial_operations = {
            "compare_strategy_shift": compare_strategy_shift,
            "analyze_holdings_exposure": analyze_holdings_exposure,
            "market_snapshot": market_snapshot,
            "simulate_account_purchase": simulate_account_purchase,
        }
        calculation = financial_operations.get(operation)
        if calculation is not None:
            result = calculation(event, load_dataset_from_s3())
        elif operation in ops.MARKET_OPERATIONS:
            result = ops.run(event, market_store.stores_from_env())
        else:
            raise ValueError(f"unsupported operation: {operation}")
        result["aws_request_id"] = request_id
        # Step Functions supplies a parent event ID for trace correlation. Legacy
        # callers omit it and retain their exact established response shape.
        if event.get("parent_event_id"):
            result["execution_event"] = {
                "event_id": f"tool.{operation}.{event.get('account_id', 'shared')}",
                "parent_id": event["parent_event_id"],
                "request_id": analysis_id,
                "kind": "tool",
                "agent": event.get("agent", "aws_financial_tools"),
                "tool_name": operation,
                "started_at": started_at.isoformat(),
                "ended_at": datetime.now(timezone.utc).isoformat(),
                "status": "completed",
                "evidence_ids": [
                    item["evidence_id"] for item in result.get("evidence", [])
                ],
                "input_summary": f"Run deterministic {operation} using versioned S3 data.",
                "output_summary": (
                    f"Completed {operation} with {len(result.get('evidence', []))} evidence records."
                ),
                "error": None,
            }
        logger.info(
            json.dumps(
                {
                    "event": "calculation_completed",
                    "analysis_id": analysis_id,
                    "operation": operation,
                    "aws_request_id": request_id,
                }
            )
        )
        return result
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        logger.exception(
            json.dumps(
                {
                    "event": "calculation_failed",
                    "analysis_id": analysis_id,
                    "operation": operation,
                    "aws_request_id": request_id,
                    "error_type": type(exc).__name__,
                }
            )
        )
        return {
            "status": "error",
            "operation": operation,
            "analysis_id": analysis_id,
            "aws_request_id": request_id,
            "error": str(exc),
        }
