import requests
from aws_lambda_powertools import Logger

from .base import Alert, BaseChannel


logger = Logger(child=True)


class TelegramChannel(BaseChannel):
    TELEGRAM_API_BASE = "https://api.telegram.org/bot"

    def __init__(self, enabled: bool, bot_token: str, chat_id: str):
        self._enabled = enabled
        self._bot_token = bot_token
        self._chat_id = chat_id

    @property
    def name(self) -> str:
        return "telegram"

    def is_enabled(self) -> bool:
        return self._enabled and bool(self._bot_token) and bool(self._chat_id)

    def send(self, alert: Alert) -> bool:
        message = self._format_message(alert)
        url = f"{self.TELEGRAM_API_BASE}{self._bot_token}/sendMessage"

        payload = {
            "chat_id": self._chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()

            result = response.json()
            if result.get("ok"):
                logger.info("Telegram message sent successfully", extra={"chat_id": self._chat_id})
                return True
            else:
                logger.error("Telegram API error", extra={"description": result.get("description")})
                return False
        except requests.RequestException as e:
            logger.error("Failed to send Telegram message", extra={"error": str(e)})
            return False

    def _format_message(self, alert: Alert) -> str:
        status_emoji = "🔴" if alert.status == "firing" else "✅"
        level_emoji = {"error": "🚨", "warning": "⚠️", "info": "ℹ️"}.get(alert.level, "📢")

        lines = [
            f"{status_emoji} {level_emoji} *{self._escape_markdown(alert.title)}*",
            "",
            f"*Status:* `{alert.status.upper()}`",
            f"*Severity:* `{alert.level.upper()}`",
        ]

        if alert.message:
            lines.append(f"*Message:* {self._escape_markdown(alert.message)}")
        if alert.value_string:
            lines.append(f"*Value:* `{alert.value_string}`")
        if alert.labels:
            labels_formatted = [f"`{k}`: {self._escape_markdown(v)}" for k, v in list(alert.labels.items())[:5]]
            lines.append("*Labels:*\n" + "\n".join(labels_formatted))
        if alert.dashboard_url:
            lines.append(f"\n[View Dashboard]({alert.dashboard_url})")
        if alert.starts_at:
            lines.append(f"\n_Started: {alert.starts_at.strftime('%Y-%m-%d %H:%M:%S UTC')}_")

        return "\n".join(lines)

    @staticmethod
    def _escape_markdown(text: str) -> str:
        special_chars = ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]
        for char in special_chars:
            text = text.replace(char, f"\\{char}")
        return text
