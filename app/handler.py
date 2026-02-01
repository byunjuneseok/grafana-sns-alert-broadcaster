import json

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from channels.base import Alert
from container import Container


logger = Logger()
tracer = Tracer()

container = Container()


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
            all_results.append(
                {
                    "alert_title": alert.title,
                    "level": alert.level,
                    "status": alert.status,
                    "channel_results": results,
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
