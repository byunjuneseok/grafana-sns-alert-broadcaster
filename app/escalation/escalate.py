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
    Escalates alert to next level.

    Input:
      - alert_id: Alert ID
      - current_level: Current escalation level
      - max_level: Maximum escalation level

    Output:
      - alert_id: Alert ID
      - new_level: New escalation level
      - should_continue: Whether to continue escalation
    """
    logger.info("Escalating alert", event=event)

    alert_id = event["alert_id"]
    current_level = event.get("current_level", 1)
    max_level = event.get("max_level", 3)

    new_level = current_level + 1
    should_continue = new_level <= max_level

    if should_continue:
        table.update_item(
            Key={"alert_id": alert_id},
            UpdateExpression="SET current_level = :level, updated_at = :updated_at",
            ExpressionAttributeValues={
                ":level": new_level,
                ":updated_at": datetime.utcnow().isoformat(),
            },
        )
        logger.info("Alert escalated", alert_id=alert_id, new_level=new_level)
    else:
        logger.warning("Max escalation level reached", alert_id=alert_id, max_level=max_level)

    return {
        "alert_id": alert_id,
        "new_level": new_level,
        "should_continue": should_continue,
    }
