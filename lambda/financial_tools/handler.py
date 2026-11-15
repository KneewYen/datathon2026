"""AWS Lambda entry point for deterministic, S3-backed financial calculations."""

from __future__ import annotations

import json
import logging

try:
    from .calculations import compare_scenarios, compare_strategy_shift
    from .data_access import load_dataset_from_s3
except ImportError:  # Lambda CodeUri places modules at the runtime root.
    from calculations import compare_scenarios, compare_strategy_shift
    from data_access import load_dataset_from_s3


logger = logging.getLogger()
logger.setLevel(logging.INFO)

OPERATIONS = {
    "compare_strategy_shift": compare_strategy_shift,
    "compare_scenarios": compare_scenarios,
}


def handler(event, context):
    operation = event.get("operation")
    analysis_id = event.get("analysis_id", "unknown")
    request_id = getattr(context, "aws_request_id", "local")
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
        if operation not in OPERATIONS:
            raise ValueError(f"unsupported operation: {operation}")
        result = OPERATIONS[operation](event, load_dataset_from_s3())
        result["aws_request_id"] = request_id
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
