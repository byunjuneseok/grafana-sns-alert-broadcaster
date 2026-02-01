from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel, Field


class Alert(BaseModel):
    title: str
    message: str = ""
    level: str = "warning"
    status: str = "firing"
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    dashboard_url: str = ""
    panel_url: str = ""
    value_string: str = ""
    fingerprint: str = ""
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @classmethod
    def from_grafana_payload(cls, payload: dict) -> "Alert":
        alerts = payload.get("alerts", [])

        if alerts:
            alert_data = alerts[0]
            labels = alert_data.get("labels", {})
            annotations = alert_data.get("annotations", {})

            severity = labels.get("severity", "warning").lower()
            if severity not in ("error", "warning", "info"):
                severity = "warning"

            starts_at = None
            ends_at = None
            if alert_data.get("startsAt"):
                try:
                    starts_at = datetime.fromisoformat(alert_data["startsAt"].replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass
            if alert_data.get("endsAt") and alert_data["endsAt"] != "0001-01-01T00:00:00Z":
                try:
                    ends_at = datetime.fromisoformat(alert_data["endsAt"].replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

            return cls(
                title=payload.get("title", labels.get("alertname", "Unknown Alert")),
                message=payload.get("message", annotations.get("summary", "")),
                level=severity,
                status=payload.get("status", alert_data.get("status", "firing")),
                labels=labels,
                annotations=annotations,
                dashboard_url=alert_data.get("dashboardURL", ""),
                panel_url=alert_data.get("panelURL", ""),
                value_string=alert_data.get("valueString", ""),
                fingerprint=alert_data.get("fingerprint", ""),
                starts_at=starts_at,
                ends_at=ends_at,
            )
        else:
            return cls(
                title=payload.get("title", payload.get("ruleName", "Unknown Alert")),
                message=payload.get("message", payload.get("ruleUrl", "")),
                level=payload.get("severity", "warning").lower(),
                status=payload.get("state", "alerting"),
                labels=payload.get("tags", {}),
            )

    def format_for_text(self) -> str:
        status_emoji = "🔴" if self.status == "firing" else "✅"
        level_emoji = {"error": "🚨", "warning": "⚠️", "info": "ℹ️"}.get(self.level, "📢")

        lines = [
            f"{status_emoji} {level_emoji} {self.title}",
            f"Status: {self.status.upper()}",
            f"Severity: {self.level.upper()}",
        ]

        if self.message:
            lines.append(f"Message: {self.message}")
        if self.value_string:
            lines.append(f"Value: {self.value_string}")
        if self.labels:
            labels_str = ", ".join(f"{k}={v}" for k, v in self.labels.items())
            lines.append(f"Labels: {labels_str}")
        if self.dashboard_url:
            lines.append(f"Dashboard: {self.dashboard_url}")

        return "\n".join(lines)


class BaseChannel(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def send(self, alert: Alert) -> bool:
        pass

    @abstractmethod
    def is_enabled(self) -> bool:
        pass
