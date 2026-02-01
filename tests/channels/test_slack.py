from unittest.mock import MagicMock, patch

import pytest

from channels.base import Alert
from channels.slack import SlackChannel


@pytest.fixture
def sample_alert():
    return Alert(
        title="Test Alert",
        message="Test message",
        level="error",
        status="firing",
        labels={"alertname": "TestAlert", "instance": "server-01"},
        dashboard_url="http://grafana/d/test",
    )


class TestSlackChannel:
    def test_name(self):
        channel = SlackChannel(enabled=True, webhook_url="https://hooks.slack.com/xxx")
        assert channel.name == "slack"

    def test_is_enabled_true(self):
        channel = SlackChannel(enabled=True, webhook_url="https://hooks.slack.com/xxx")
        assert channel.is_enabled() is True

    def test_is_enabled_false_when_disabled(self):
        channel = SlackChannel(enabled=False, webhook_url="https://hooks.slack.com/xxx")
        assert channel.is_enabled() is False

    def test_is_enabled_false_when_missing_webhook(self):
        channel = SlackChannel(enabled=True, webhook_url="")
        assert channel.is_enabled() is False

    @patch("channels.slack.requests.post")
    def test_send_success(self, mock_post, sample_alert):
        mock_response = MagicMock()
        mock_response.text = "ok"
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        channel = SlackChannel(enabled=True, webhook_url="https://hooks.slack.com/xxx")
        result = channel.send(sample_alert)

        assert result is True
        mock_post.assert_called_once()

    @patch("channels.slack.requests.post")
    def test_send_failure(self, mock_post, sample_alert):
        mock_response = MagicMock()
        mock_response.text = "invalid_payload"
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        channel = SlackChannel(enabled=True, webhook_url="https://hooks.slack.com/xxx")
        result = channel.send(sample_alert)

        assert result is False

    @patch("channels.slack.requests.post")
    def test_send_request_exception(self, mock_post, sample_alert):
        import requests

        mock_post.side_effect = requests.RequestException("Connection error")

        channel = SlackChannel(enabled=True, webhook_url="https://hooks.slack.com/xxx")
        result = channel.send(sample_alert)

        assert result is False

    def test_build_payload_structure(self, sample_alert):
        channel = SlackChannel(enabled=True, webhook_url="https://hooks.slack.com/xxx")
        payload = channel._build_payload(sample_alert)

        assert "attachments" in payload
        assert len(payload["attachments"]) == 1
        attachment = payload["attachments"][0]
        assert "color" in attachment
        assert "blocks" in attachment
        assert attachment["color"] == "#dc3545"

    def test_build_payload_warning_color(self):
        alert = Alert(
            title="Warning Alert",
            message="Warning message",
            level="warning",
            status="firing",
        )

        channel = SlackChannel(enabled=True, webhook_url="https://hooks.slack.com/xxx")
        payload = channel._build_payload(alert)

        assert payload["attachments"][0]["color"] == "#ffc107"

    def test_build_payload_info_color(self):
        alert = Alert(
            title="Info Alert",
            message="Info message",
            level="info",
            status="firing",
        )

        channel = SlackChannel(enabled=True, webhook_url="https://hooks.slack.com/xxx")
        payload = channel._build_payload(alert)

        assert payload["attachments"][0]["color"] == "#17a2b8"
