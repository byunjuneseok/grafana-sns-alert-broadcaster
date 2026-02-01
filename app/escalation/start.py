import os
import time
import uuid
from datetime import datetime

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
tracer = Tracer()

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("ALERTS_TABLE_NAME", "alerts"))

# TTL: 24 hours
TTL_SECONDS = 24 * 60 * 60


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    Starts escalation by creating alert record in DynamoDB.

    Input:
      - alert_title: Alert title
      - alert_description: Alert description
      - severity: Alert severity
      - fingerprint: Alert fingerprint (used as alert_id)

    Output:
      - alert_id: Created alert ID
      - status: Alert status (pending)
      - current_level: Current escalation level (1)
    """
    logger.info("Starting escalation", event=event)

    alert_id = event.get("fingerprint") or str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    ttl = int(time.time()) + TTL_SECONDS

    item = {
        "alert_id": alert_id,
        "status": "pending",
        "current_level": 1,
        "alert_title": event.get("alert_title", "Unknown Alert"),
        "alert_description": event.get("alert_description", ""),
        "severity": event.get("severity", "critical"),
        "created_at": now,
        "updated_at": now,
        "ttl": ttl,
    }

    table.put_item(Item=item)
    logger.info("Alert record created", alert_id=alert_id)

    return {
        "alert_id": alert_id,
        "status": "pending",
        "current_level": 1,
        "alert_title": item["alert_title"],
        "alert_description": item["alert_description"],
    }
