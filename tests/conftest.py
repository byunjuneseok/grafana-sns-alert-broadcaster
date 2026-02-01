import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# Disable X-Ray tracing for tests
os.environ["POWERTOOLS_TRACE_DISABLED"] = "true"

# Add app directory to path for imports
app_dir = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(app_dir))


@pytest.fixture
def sample_grafana_payload():
    return {
        "status": "firing",
        "title": "[FIRING:1] High CPU",
        "message": "CPU usage is high",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "HighCPU",
                    "severity": "warning",
                    "instance": "server-01",
                },
                "annotations": {
                    "summary": "CPU is above 80%",
                },
                "startsAt": "2024-01-15T10:00:00Z",
                "dashboardURL": "http://grafana/d/abc123",
                "valueString": "95.5",
                "fingerprint": "abc123",
            }
        ],
    }


@pytest.fixture
def sample_sns_event(sample_grafana_payload):
    import json

    return {
        "Records": [
            {
                "EventSource": "aws:sns",
                "Sns": {
                    "Message": json.dumps(sample_grafana_payload),
                },
            }
        ]
    }


@pytest.fixture
def mock_lambda_context():
    context = MagicMock()
    context.function_name = "test-function"
    context.memory_limit_in_mb = 128
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test-function"
    context.aws_request_id = "test-request-id"
    return context
