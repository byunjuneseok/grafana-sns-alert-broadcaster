import os
from datetime import datetime

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
tracer = Tracer()

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("ALERTS_TABLE_NAME", "alerts"))


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    Checks if alert has been acknowledged.

    Input:
      - alert_id: Alert ID to check

    Output:
      - is_acked: Boolean indicating if alert is acknowledged
      - status: Current alert status
      - acked_by: Who acknowledged (if acked)
    """
    logger.info("Checking ACK status", event=event)

    alert_id = event["alert_id"]

    try:
        response = table.get_item(Key={"PK": f"ALERT#{alert_id}", "SK": "METADATA"})
        item = response.get("Item")

        if not item:
            logger.warning("Alert not found", alert_id=alert_id)
            return {
                "is_acked": False,
                "status": "not_found",
                "acked_by": None,
            }

        status = item.get("status", "pending")
        is_acked = status == "acked"

        logger.info("ACK status checked", alert_id=alert_id, status=status, is_acked=is_acked)

        return {
            "is_acked": is_acked,
            "status": status,
            "acked_by": item.get("acked_by"),
            "acked_at": item.get("acked_at"),
        }

    except Exception as e:
        logger.exception("Failed to check ACK status")
        return {
            "is_acked": False,
            "status": "error",
            "error": str(e),
        }
