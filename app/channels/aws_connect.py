import boto3
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

from .base import Alert, BaseChannel


logger = Logger(child=True)


class AWSConnectChannel(BaseChannel):
    def __init__(
        self,
        enabled: bool,
        instance_id: str,
        contact_flow_id: str,
        source_phone_number: str,
        destination_phone_number: str,
    ):
        self._enabled = enabled
        self._instance_id = instance_id
        self._contact_flow_id = contact_flow_id
        self._source_phone_number = source_phone_number
        self._destination_phone_number = destination_phone_number
        self._connect_client = boto3.client("connect") if enabled else None

    @property
    def name(self) -> str:
        return "aws_connect"

    def is_enabled(self) -> bool:
        return (
            self._enabled
            and bool(self._instance_id)
            and bool(self._contact_flow_id)
            and bool(self._source_phone_number)
            and bool(self._destination_phone_number)
        )

    def send(self, alert: Alert) -> bool:
        if not self._connect_client:
            logger.error("AWS Connect client not initialized")
            return False

        attributes = self._build_attributes(alert)

        try:
            response = self._connect_client.start_outbound_voice_contact(
                DestinationPhoneNumber=self._destination_phone_number,
                ContactFlowId=self._contact_flow_id,
                InstanceId=self._instance_id,
                SourcePhoneNumber=self._source_phone_number,
                Attributes=attributes,
            )
            contact_id = response.get("ContactId")
            logger.info("AWS Connect call initiated", extra={"contact_id": contact_id})
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(
                "Failed to initiate AWS Connect call", extra={"error_code": error_code, "error_message": error_message}
            )
            return False
        except Exception as e:
            logger.error("Unexpected error initiating AWS Connect call", extra={"error": str(e)})
            return False

    def _build_attributes(self, alert: Alert) -> dict[str, str]:
        message = self._build_voice_message(alert)

        attributes = {
            "alertTitle": alert.title[:200],
            "alertMessage": message[:500],
            "alertSeverity": alert.level.upper(),
            "alertStatus": alert.status.upper(),
        }

        if alert.labels.get("alertname"):
            attributes["alertName"] = alert.labels["alertname"][:100]
        if alert.labels.get("instance"):
            attributes["instance"] = alert.labels["instance"][:100]
        if alert.labels.get("job"):
            attributes["job"] = alert.labels["job"][:100]

        return attributes

    def _build_voice_message(self, alert: Alert) -> str:
        status_text = "firing" if alert.status == "firing" else "resolved"

        parts = [
            f"Alert {status_text}.",
            f"Severity: {alert.level}.",
            f"Title: {alert.title}.",
        ]

        if alert.message:
            clean_message = alert.message.replace("\n", " ").strip()
            parts.append(f"Message: {clean_message}.")
        if alert.labels.get("instance"):
            parts.append(f"Instance: {alert.labels['instance']}.")

        return " ".join(parts)
