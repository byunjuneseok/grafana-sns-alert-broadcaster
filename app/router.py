from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from aws_lambda_powertools import Logger

from channels.base import Alert, BaseChannel


logger = Logger(child=True)


class Router:
    def __init__(
        self,
        channels: list[BaseChannel],
        routing_config: Any,
        default_level: str = "warning",
        max_workers: int = 5,
    ):
        self._channels = {ch.name: ch for ch in channels}
        self._routing_config = routing_config
        self._default_level = default_level
        self._max_workers = max_workers

    def _get_routing_for_level(self, level: str) -> list[str]:
        if isinstance(self._routing_config, dict):
            return self._routing_config.get(level) or self._routing_config.get(self._default_level) or []

        try:
            if hasattr(self._routing_config, level):
                result = getattr(self._routing_config, level)
                return result() if callable(result) else (result or [])
        except (AttributeError, TypeError):
            pass

        try:
            if hasattr(self._routing_config, self._default_level):
                result = getattr(self._routing_config, self._default_level)
                return result() if callable(result) else (result or [])
        except (AttributeError, TypeError):
            pass

        return []

    def get_target_channels(self, level: str) -> list[BaseChannel]:
        channel_names = self._get_routing_for_level(level)
        channels = []

        for name in channel_names:
            channel = self._channels.get(name)
            if channel and channel.is_enabled():
                channels.append(channel)

        return channels

    def route(self, alert: Alert) -> dict[str, bool]:
        target_channels = self.get_target_channels(alert.level)

        if not target_channels:
            logger.warning("No channels configured for level", extra={"level": alert.level})
            return {}

        logger.info(
            "Routing alert",
            extra={
                "alert_title": alert.title,
                "level": alert.level,
                "channels": [ch.name for ch in target_channels],
            },
        )

        results = self._send_parallel(alert, target_channels)

        successful = [ch for ch, success in results.items() if success]
        failed = [ch for ch, success in results.items() if not success]

        if successful:
            logger.info("Successfully sent to channels", extra={"channels": successful})
        if failed:
            logger.error("Failed to send to channels", extra={"channels": failed})

        return results

    def _send_parallel(self, alert: Alert, channels: list[BaseChannel]) -> dict[str, bool]:
        results: dict[str, bool] = {}

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            futures = {executor.submit(self._send_with_retry, ch, alert): ch.name for ch in channels}

            for future in as_completed(futures):
                channel_name = futures[future]
                try:
                    results[channel_name] = future.result()
                except Exception as e:
                    logger.error("Exception sending to channel", extra={"channel": channel_name, "error": str(e)})
                    results[channel_name] = False

        return results

    def _send_with_retry(self, channel: BaseChannel, alert: Alert, max_retries: int = 2) -> bool:
        for attempt in range(max_retries + 1):
            try:
                if channel.send(alert):
                    return True
                logger.warning(
                    "Channel returned False",
                    extra={"channel": channel.name, "attempt": attempt + 1, "max_retries": max_retries + 1},
                )
            except Exception as e:
                logger.warning(
                    "Channel raised exception",
                    extra={"channel": channel.name, "attempt": attempt + 1, "error": str(e)},
                )

        return False
