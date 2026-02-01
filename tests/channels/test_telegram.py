from unittest.mock import MagicMock, patch

import pytest

from channels.base import Alert
from channels.telegram import TelegramChannel


@pytest.fixture
def sample_alert():
    return Alert(
        title="Test Alert",
        message="Test message",
        level="warning",
        status="firing",
        labels={"alertname": "TestAlert", "instance": "server-01"},
        dashboard_url="http://grafana/d/test",
    )


class TestTelegramChannel:
    def test_name(self):
        channel = TelegramChannel(enabled=True, bot_token="token", chat_id="123")
        assert channel.name == "telegram"

    def test_is_enabled_true(self):
        channel = TelegramChannel(enabled=True, bot_token="token", chat_id="123")
        assert channel.is_enabled() is True

    def test_is_enabled_false_when_disabled(self):
        channel = TelegramChannel(enabled=False, bot_token="token", chat_id="123")
        assert channel.is_enabled() is False

    def test_is_enabled_false_when_missing_token(self):
        channel = TelegramChannel(enabled=True, bot_token="", chat_id="123")
        assert channel.is_enabled() is False

    def test_is_enabled_false_when_missing_chat_id(self):
        channel = TelegramChannel(enabled=True, bot_token="token", chat_id="")
        assert channel.is_enabled() is False

    @patch("channels.telegram.requests.post")
    def test_send_success(self, mock_post, sample_alert):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 123}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        channel = TelegramChannel(enabled=True, bot_token="test-token", chat_id="123456789")
        result = channel.send(sample_alert)

        assert result is True
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "test-token" in call_args[0][0]
        assert call_args[1]["json"]["chat_id"] == "123456789"

    @patch("channels.telegram.requests.post")
    def test_send_api_error(self, mock_post, sample_alert):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": False, "description": "Bad Request"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        channel = TelegramChannel(enabled=True, bot_token="test-token", chat_id="123456789")
        result = channel.send(sample_alert)

        assert result is False

    @patch("channels.telegram.requests.post")
    def test_send_request_exception(self, mock_post, sample_alert):
        import requests

        mock_post.side_effect = requests.RequestException("Connection error")

        channel = TelegramChannel(enabled=True, bot_token="test-token", chat_id="123456789")
        result = channel.send(sample_alert)

        assert result is False

    def test_escape_markdown(self):
        channel = TelegramChannel(enabled=True, bot_token="token", chat_id="123")

        text = "Hello *world* [link](url) _italic_"
        escaped = channel._escape_markdown(text)

        assert "\\*" in escaped
        assert "\\[" in escaped
        assert "\\_" in escaped
