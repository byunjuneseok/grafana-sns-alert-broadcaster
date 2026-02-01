from typing import Any

import requests
from aws_lambda_powertools import Logger

from .base import Alert, BaseChannel


logger = Logger(child=True)


class SlackChannel(BaseChannel):
    def __init__(self, enabled: bool, webhook_url: str):
        self._enabled = enabled
        self._webhook_url = webhook_url

    @property
    def name(self) -> str:
        return "slack"

    def is_enabled(self) -> bool:
        return self._enabled and bool(self._webhook_url)

    def send(self, alert: Alert) -> bool:
        payload = self._build_payload(alert)

        try:
            response = requests.post(
                self._webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()

            if response.text == "ok":
                logger.info("Slack message sent successfully")
                return True
            else:
                logger.error("Slack API returned unexpected response", extra={"response": response.text})
                return False
        except requests.RequestException as e:
            logger.error("Failed to send Slack message", extra={"error": str(e)})
            return False

    def _build_payload(self, alert: Alert) -> dict[str, Any]:
        status_emoji = ":red_circle:" if alert.status == "firing" else ":white_check_mark:"
        level_emoji = {
            "error": ":rotating_light:",
            "warning": ":warning:",
            "info": ":information_source:",
        }.get(alert.level, ":bell:")

        color = {"error": "#dc3545", "warning": "#ffc107", "info": "#17a2b8"}.get(alert.level, "#6c757d")

        blocks: list[dict[str, Any]] = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{status_emoji} {level_emoji} {alert.title}", "emoji": True},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Status:*\n`{alert.status.upper()}`"},
                    {"type": "mrkdwn", "text": f"*Severity:*\n`{alert.level.upper()}`"},
                ],
            },
        ]

        if alert.message:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Message:*\n{alert.message}"}})
        if alert.value_string:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Value:* `{alert.value_string}`"}})
        if alert.labels:
            labels_text = "\n".join(f"• `{k}`: {v}" for k, v in list(alert.labels.items())[:10])
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Labels:*\n{labels_text}"}})
        if alert.dashboard_url:
            blocks.append(
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "View Dashboard", "emoji": True},
                            "url": alert.dashboard_url,
                            "style": "primary",
                        }
                    ],
                }
            )
        if alert.starts_at:
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f"Started: {alert.starts_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"}
                    ],
                }
            )

        blocks.append({"type": "divider"})

        return {"attachments": [{"color": color, "blocks": blocks}]}
