from unittest.mock import MagicMock

import pytest

from channels.base import Alert
from router import Router


@pytest.fixture
def sample_alert():
    return Alert(
        title="Test Alert",
        message="Test message",
        level="warning",
        status="firing",
        labels={"alertname": "TestAlert"},
    )


@pytest.fixture
def mock_routing_config():
    config = MagicMock()
    config.error = MagicMock(return_value=["telegram", "slack", "aws_connect"])
    config.warning = MagicMock(return_value=["telegram", "slack"])
    config.info = MagicMock(return_value=["slack"])
    return config


class TestRouter:
    def test_get_target_channels_warning(self, mock_routing_config):
        mock_telegram = MagicMock()
        mock_telegram.name = "telegram"
        mock_telegram.is_enabled.return_value = True

        mock_slack = MagicMock()
        mock_slack.name = "slack"
        mock_slack.is_enabled.return_value = True

        router = Router(
            channels=[mock_telegram, mock_slack],
            routing_config=mock_routing_config,
            default_level="warning",
        )

        channels = router.get_target_channels("warning")

        assert len(channels) == 2
        assert mock_telegram in channels
        assert mock_slack in channels

    def test_get_target_channels_filters_disabled(self, mock_routing_config):
        mock_telegram = MagicMock()
        mock_telegram.name = "telegram"
        mock_telegram.is_enabled.return_value = True

        mock_slack = MagicMock()
        mock_slack.name = "slack"
        mock_slack.is_enabled.return_value = False

        router = Router(
            channels=[mock_telegram, mock_slack],
            routing_config=mock_routing_config,
            default_level="warning",
        )

        channels = router.get_target_channels("warning")

        assert len(channels) == 1
        assert mock_telegram in channels
        assert mock_slack not in channels

    def test_route_sends_to_channels(self, sample_alert, mock_routing_config):
        mock_telegram = MagicMock()
        mock_telegram.name = "telegram"
        mock_telegram.is_enabled.return_value = True
        mock_telegram.send.return_value = True

        mock_slack = MagicMock()
        mock_slack.name = "slack"
        mock_slack.is_enabled.return_value = True
        mock_slack.send.return_value = True

        router = Router(
            channels=[mock_telegram, mock_slack],
            routing_config=mock_routing_config,
            default_level="warning",
        )

        results = router.route(sample_alert)

        assert results["telegram"] is True
        assert results["slack"] is True
        mock_telegram.send.assert_called()
        mock_slack.send.assert_called()

    def test_route_handles_channel_failure(self, sample_alert, mock_routing_config):
        mock_telegram = MagicMock()
        mock_telegram.name = "telegram"
        mock_telegram.is_enabled.return_value = True
        mock_telegram.send.return_value = False

        router = Router(
            channels=[mock_telegram],
            routing_config=mock_routing_config,
            default_level="warning",
        )

        results = router.route(sample_alert)

        assert results["telegram"] is False

    def test_route_no_channels_for_level(self, sample_alert):
        mock_routing_config = MagicMock()
        mock_routing_config.unknown = MagicMock(side_effect=AttributeError)
        mock_routing_config.warning = MagicMock(return_value=[])

        sample_alert.level = "unknown"

        router = Router(
            channels=[],
            routing_config=mock_routing_config,
            default_level="warning",
        )

        results = router.route(sample_alert)

        assert results == {}

    def test_retry_on_failure(self, sample_alert, mock_routing_config):
        mock_telegram = MagicMock()
        mock_telegram.name = "telegram"
        mock_telegram.is_enabled.return_value = True
        mock_telegram.send.side_effect = [False, False, True]

        router = Router(
            channels=[mock_telegram],
            routing_config=mock_routing_config,
            default_level="warning",
        )

        results = router.route(sample_alert)

        assert results["telegram"] is True
        assert mock_telegram.send.call_count == 3
