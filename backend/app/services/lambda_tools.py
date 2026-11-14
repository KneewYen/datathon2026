"""Invokes AWS Lambda financial tools. Numbers come from here, never from the LLM."""
import json
import os
from typing import Any, Dict

import boto3


def invoke(operation: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    resp = boto3.client("lambda", region_name=os.getenv("AWS_REGION")).invoke(
        FunctionName=os.getenv("LAMBDA_FUNCTION_NAME"),
        Payload=json.dumps({"operation": operation, **payload}),
    )
    return json.loads(resp["Payload"].read())
