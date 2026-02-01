import json
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
    logger.info("Received ACK request", event=event)

    # Extract alert_id from path parameters
    alert_id = event.get("pathParameters", {}).get("alert_id")
    if not alert_id:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "alert_id is required"}),
        }

    # Extract acked_by from body or query params
    body = {}
    if event.get("body"):
        body = json.loads(event["body"])

    acked_by = body.get("acked_by") or event.get("queryStringParameters", {}).get("acked_by", "unknown")

    try:
        # Update alert status in DynamoDB
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

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "message": "Alert acknowledged",
                    "alert_id": alert_id,
                    "acked_by": acked_by,
                }
            ),
        }

    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        logger.warning("Alert not found", alert_id=alert_id)
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Alert not found"}),
        }
    except Exception as e:
        logger.exception("Failed to acknowledge alert")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }
