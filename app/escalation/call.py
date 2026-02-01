import os

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
tracer = Tracer()

connect = boto3.client("connect")


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    Makes AWS Connect outbound call to on-call person.

    Input:
      - alert_id: Alert ID
      - alert_title: Alert title
      - phone_number: Destination phone number
      - current_level: Current escalation level

    Output:
      - contact_id: AWS Connect contact ID
      - call_status: Call initiation status
    """
    logger.info("Making escalation call", event=event)

    alert_id = event["alert_id"]
    alert_title = event.get("alert_title", "Alert")
    phone_number = event["phone_number"]
    current_level = event.get("current_level", 1)

    instance_id = os.environ["AWS_CONNECT_INSTANCE_ID"]
    contact_flow_id = os.environ["AWS_CONNECT_CONTACT_FLOW_ID"]
    source_phone = os.environ["AWS_CONNECT_SOURCE_PHONE"]

    try:
        response = connect.start_outbound_voice_contact(
            DestinationPhoneNumber=phone_number,
            ContactFlowId=contact_flow_id,
            InstanceId=instance_id,
            SourcePhoneNumber=source_phone,
            Attributes={
                "alert_id": alert_id,
                "alert_title": alert_title,
                "escalation_level": str(current_level),
            },
        )

        contact_id = response["ContactId"]
        logger.info("Call initiated", contact_id=contact_id, phone_number=phone_number)

        return {
            "contact_id": contact_id,
            "call_status": "initiated",
            "phone_number": phone_number,
        }

    except Exception as e:
        logger.exception("Failed to initiate call")
        return {
            "contact_id": None,
            "call_status": "failed",
            "error": str(e),
            "phone_number": phone_number,
        }
