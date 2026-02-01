import json
import os

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from channels.base import Alert
from container import Container


logger = Logger()
tracer = Tracer()

container = Container()
sfn_client = boto3.client("stepfunctions")


def should_escalate(alert: Alert) -> bool:
    """Check if alert should trigger escalation."""
    escalation_enabled = os.environ.get("ESCALATION_ENABLED", "false").lower() == "true"
    if not escalation_enabled:
        return False

    trigger_levels = os.environ.get("ESCALATION_TRIGGER_LEVELS", "critical").split(",")
    return alert.level in trigger_levels and alert.status == "firing"


def start_escalation(alert: Alert) -> dict | None:
    """Start Step Functions escalation workflow."""
    state_machine_arn = os.environ.get("ESCALATION_STATE_MACHINE_ARN")
    if not state_machine_arn:
        logger.warning("ESCALATION_STATE_MACHINE_ARN not configured")
        return None

    input_data = {
        "alert_title": alert.title,
        "alert_description": alert.description,
        "severity": alert.level,
        "fingerprint": alert.fingerprint,
        "oncall": {
            "level1_phone": os.environ.get("ONCALL_L1_PHONE", ""),
            "level2_phone": os.environ.get("ONCALL_L2_PHONE", ""),
            "level3_phone": os.environ.get("ONCALL_L3_PHONE", ""),
            "max_level": int(os.environ.get("ESCALATION_MAX_LEVEL", "3")),
        },
    }

    try:
        response = sfn_client.start_execution(
            stateMachineArn=state_machine_arn,
            name=f"alert-{alert.fingerprint[:50]}-{int(__import__('time').time())}",
            input=json.dumps(input_data),
        )
        logger.info("Escalation started", execution_arn=response["executionArn"])
        return {"execution_arn": response["executionArn"]}
    except Exception as e:
        logger.exception("Failed to start escalation")
        return {"error": str(e)}


def parse_sns_event(event: dict) -> list[dict]:
    payloads = []

    for record in event.get("Records", []):
        if record.get("EventSource") != "aws:sns":
            continue

        sns_message = record.get("Sns", {}).get("Message", "{}")

        try:
            payload = json.loads(sns_message)
            payloads.append(payload)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse SNS message as JSON", extra={"error": str(e)})
            payloads.append({"message": sns_message, "title": "Alert"})

    return payloads


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    logger.info("Received event", extra={"event": json.dumps(event)[:1000]})

    try:
        router = container.router()
        payloads = parse_sns_event(event)

        if not payloads:
            logger.warning("No valid payloads found in event")
            return {"statusCode": 200, "body": json.dumps({"message": "No payloads to process"})}

        all_results = []

        for payload in payloads:
            logger.info("Processing payload", extra={"payload": json.dumps(payload)[:500]})

            alert = Alert.from_grafana_payload(payload)
            logger.info("Parsed alert", extra={"title": alert.title, "level": alert.level, "status": alert.status})

            results = router.route(alert)

            # Check if escalation should be triggered
            escalation_result = None
            if should_escalate(alert):
                logger.info("Triggering escalation", alert_title=alert.title, level=alert.level)
                escalation_result = start_escalation(alert)

            all_results.append(
                {
                    "alert_title": alert.title,
                    "level": alert.level,
                    "status": alert.status,
                    "channel_results": results,
                    "escalation": escalation_result,
                }
            )

        all_successful = all(all(r["channel_results"].values()) for r in all_results if r["channel_results"])

        return {
            "statusCode": 200 if all_successful else 207,
            "body": json.dumps(
                {
                    "message": "Processed" if all_successful else "Partially processed",
                    "results": all_results,
                }
            ),
        }

    except Exception as e:
        logger.exception("Error processing event")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
