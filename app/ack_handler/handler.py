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
    Handles ACK from AWS Connect Contact Flow.

    AWS Connect invokes Lambda with contact attributes.
    Expected attributes:
      - alert_id: The alert ID to acknowledge
      - acked_by: Phone number or name of the person who acknowledged

    Returns a response that AWS Connect can use in the contact flow.
    """
    logger.info("Received ACK request from AWS Connect", event=event)

    # Extract from AWS Connect contact attributes
    details = event.get("Details", {})
    contact_data = details.get("ContactData", {})
    attributes = contact_data.get("Attributes", {})

    alert_id = attributes.get("alert_id")
    acked_by = attributes.get("acked_by") or contact_data.get("CustomerEndpoint", {}).get("Address", "unknown")

    if not alert_id:
        logger.error("alert_id not provided in contact attributes")
        return {"status": "error", "message": "alert_id is required"}

    try:
        response = table.update_item(
            Key={"alert_id": alert_id},
            UpdateExpression="SET #status = :status, acked_by = :acked_by, acked_at = :acked_at",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "acked",
                ":acked_by": acked_by,
                ":acked_at": datetime.utcnow().isoformat(),
            },
            ConditionExpression="attribute_exists(alert_id)",
            ReturnValues="ALL_NEW",
        )

        logger.info("Alert acknowledged", alert_id=alert_id, acked_by=acked_by)

        # Return response for AWS Connect
        return {
            "status": "success",
            "message": "Alert acknowledged",
            "alert_id": alert_id,
            "acked_by": acked_by,
        }

    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        logger.warning("Alert not found", alert_id=alert_id)
        return {"status": "error", "message": "Alert not found"}

    except Exception as e:
        logger.exception("Failed to acknowledge alert")
        return {"status": "error", "message": str(e)}
