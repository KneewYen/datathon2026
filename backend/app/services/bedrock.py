"""Amazon Bedrock client: LLM reasoning for all agents."""
import os

import boto3


def client():
    return boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION"))
