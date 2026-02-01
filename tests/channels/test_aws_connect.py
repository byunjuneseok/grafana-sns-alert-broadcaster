from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from channels.aws_connect import AWSConnectChannel
from channels.base import Alert


@pytest.fixture
def sample_alert():
    return Alert(
        title="Critical Alert",
        message="Database connection failed",
        level="error",
        status="firing",
        labels={"alertname": "DBConnection", "instance": "db-server-01", "job": "postgres"},
    )


class TestAWSConnectChannel:
    def test_name(self):
        channel = AWSConnectChannel(
            enabled=False,
            instance_id="",
            contact_flow_id="",
            source_phone_number="",
            destination_phone_number="",
        )
        assert channel.name == "aws_connect"

    def test_is_enabled_true(self):
        channel = AWSConnectChannel(
            enabled=True,
            instance_id="instance-id",
            contact_flow_id="flow-id",
            source_phone_number="+15551234567",
            destination_phone_number="+15559876543",
        )
        assert channel.is_enabled() is True

    def test_is_enabled_false_when_disabled(self):
        channel = AWSConnectChannel(
            enabled=False,
            instance_id="instance-id",
            contact_flow_id="flow-id",
            source_phone_number="+15551234567",
            destination_phone_number="+15559876543",
        )
        assert channel.is_enabled() is False

    def test_is_enabled_false_when_missing_config(self):
        channel = AWSConnectChannel(
            enabled=True,
            instance_id="",
            contact_flow_id="flow-id",
            source_phone_number="+15551234567",
            destination_phone_number="+15559876543",
        )
        assert channel.is_enabled() is False

    @patch("channels.aws_connect.boto3.client")
    def test_send_success(self, mock_boto_client, sample_alert):
        mock_connect = MagicMock()
        mock_connect.start_outbound_voice_contact.return_value = {"ContactId": "test-contact-id"}
        mock_boto_client.return_value = mock_connect

        channel = AWSConnectChannel(
            enabled=True,
            instance_id="instance-id",
            contact_flow_id="flow-id",
            source_phone_number="+15551234567",
            destination_phone_number="+15559876543",
        )
        result = channel.send(sample_alert)

        assert result is True
        mock_connect.start_outbound_voice_contact.assert_called_once()

    @patch("channels.aws_connect.boto3.client")
    def test_send_client_error(self, mock_boto_client, sample_alert):
        mock_connect = MagicMock()
        mock_connect.start_outbound_voice_contact.side_effect = ClientError(
            {"Error": {"Code": "InvalidParameterException", "Message": "Invalid phone"}},
            "StartOutboundVoiceContact",
        )
        mock_boto_client.return_value = mock_connect

        channel = AWSConnectChannel(
            enabled=True,
            instance_id="instance-id",
            contact_flow_id="flow-id",
            source_phone_number="+15551234567",
            destination_phone_number="+15559876543",
        )
        result = channel.send(sample_alert)

        assert result is False

    @patch("channels.aws_connect.boto3.client")
    def test_build_attributes(self, mock_boto_client, sample_alert):
        mock_boto_client.return_value = MagicMock()

        channel = AWSConnectChannel(
            enabled=True,
            instance_id="instance-id",
            contact_flow_id="flow-id",
            source_phone_number="+15551234567",
            destination_phone_number="+15559876543",
        )
        attributes = channel._build_attributes(sample_alert)

        assert attributes["alertTitle"] == "Critical Alert"
        assert "ERROR" in attributes["alertSeverity"]
        assert "FIRING" in attributes["alertStatus"]
        assert attributes["alertName"] == "DBConnection"
        assert attributes["instance"] == "db-server-01"

    @patch("channels.aws_connect.boto3.client")
    def test_build_voice_message(self, mock_boto_client, sample_alert):
        mock_boto_client.return_value = MagicMock()

        channel = AWSConnectChannel(
            enabled=True,
            instance_id="instance-id",
            contact_flow_id="flow-id",
            source_phone_number="+15551234567",
            destination_phone_number="+15559876543",
        )
        message = channel._build_voice_message(sample_alert)

        assert "firing" in message.lower()
        assert "error" in message.lower()
        assert "Critical Alert" in message
