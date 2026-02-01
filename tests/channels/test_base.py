from channels.base import Alert


class TestAlert:
    def test_from_grafana_unified_alerting_payload(self, sample_grafana_payload):
        alert = Alert.from_grafana_payload(sample_grafana_payload)

        assert alert.title == "[FIRING:1] High CPU"
        assert alert.message == "CPU usage is high"
        assert alert.level == "warning"
        assert alert.status == "firing"
        assert alert.labels["alertname"] == "HighCPU"
        assert alert.labels["instance"] == "server-01"
        assert alert.annotations["summary"] == "CPU is above 80%"
        assert alert.dashboard_url == "http://grafana/d/abc123"
        assert alert.value_string == "95.5"
        assert alert.fingerprint == "abc123"
        assert alert.starts_at is not None

    def test_from_grafana_legacy_payload(self):
        payload = {
            "title": "Legacy Alert",
            "ruleName": "CPU Alert",
            "message": "CPU is high",
            "ruleUrl": "http://grafana/alerts/1",
            "state": "alerting",
            "severity": "error",
            "tags": {"env": "production"},
        }

        alert = Alert.from_grafana_payload(payload)

        assert alert.title == "Legacy Alert"
        assert alert.message == "CPU is high"
        assert alert.level == "error"
        assert alert.status == "alerting"
        assert alert.labels["env"] == "production"

    def test_default_severity_when_invalid(self):
        payload = {
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"severity": "critical"},
                }
            ]
        }

        alert = Alert.from_grafana_payload(payload)

        assert alert.level == "warning"

    def test_format_for_text_firing(self):
        alert = Alert(
            title="Test Alert",
            message="Something went wrong",
            level="error",
            status="firing",
            labels={"instance": "server-01", "job": "node"},
            value_string="95.5%",
            dashboard_url="http://grafana/d/test",
        )

        text = alert.format_for_text()

        assert "🔴" in text
        assert "🚨" in text
        assert "Test Alert" in text
        assert "FIRING" in text
        assert "ERROR" in text

    def test_format_for_text_resolved(self):
        alert = Alert(
            title="Test Alert",
            message="All good now",
            level="info",
            status="resolved",
        )

        text = alert.format_for_text()

        assert "✅" in text
        assert "ℹ️" in text
        assert "RESOLVED" in text

    def test_empty_payload_handling(self):
        payload = {}

        alert = Alert.from_grafana_payload(payload)

        assert alert.title == "Unknown Alert"
        assert alert.level == "warning"
        assert alert.status == "alerting"
