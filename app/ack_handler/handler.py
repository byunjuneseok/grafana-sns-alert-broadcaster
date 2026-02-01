import os
from datetime import datetime

import boto3
import requests
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
tracer = Tracer()

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("ALERTS_TABLE_NAME", "alerts"))


def send_slack_ack_notification(alert_id: str, alert_title: str, acked_by: str) -> bool:
    """Send ACK notification to Slack."""
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL not configured, skipping Slack notification")
        return False

    message = {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":white_check_mark: *Alert Acknowledged*\n*{alert_title}*",
                },
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"*Acknowledged by:* {acked_by}"},
                    {"type": "mrkdwn", "text": f"*Alert ID:* {alert_id}"},
                    {"type": "mrkdwn", "text": f"*Time:* {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"},
                ],
            },
        ]
    }

    try:
        response = requests.post(webhook_url, json=message, timeout=10)
        response.raise_for_status()
        logger.info("Slack ACK notification sent")
        return True
    except Exception as e:
        logger.exception("Failed to send Slack ACK notification")
        return False


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

        # Get alert title from updated item
        updated_item = response.get("Attributes", {})
        alert_title = updated_item.get("alert_title", "Unknown Alert")

        # Send Slack notification
        send_slack_ack_notification(alert_id, alert_title, acked_by)

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
