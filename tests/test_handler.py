import json
from unittest.mock import MagicMock, patch

from handler import lambda_handler, parse_sns_event


class TestParseSNSEvent:
    def test_parse_valid_sns_event(self, sample_sns_event):
        payloads = parse_sns_event(sample_sns_event)

        assert len(payloads) == 1
        assert payloads[0]["title"] == "[FIRING:1] High CPU"
        assert payloads[0]["status"] == "firing"

    def test_parse_multiple_records(self):
        event = {
            "Records": [
                {"EventSource": "aws:sns", "Sns": {"Message": json.dumps({"title": "Alert 1"})}},
                {"EventSource": "aws:sns", "Sns": {"Message": json.dumps({"title": "Alert 2"})}},
            ]
        }

        payloads = parse_sns_event(event)

        assert len(payloads) == 2
        assert payloads[0]["title"] == "Alert 1"
        assert payloads[1]["title"] == "Alert 2"

    def test_skip_non_sns_records(self):
        event = {
            "Records": [
                {"EventSource": "aws:sqs", "Body": "some message"},
                {"EventSource": "aws:sns", "Sns": {"Message": json.dumps({"title": "SNS Alert"})}},
            ]
        }

        payloads = parse_sns_event(event)

        assert len(payloads) == 1
        assert payloads[0]["title"] == "SNS Alert"

    def test_handle_invalid_json(self):
        event = {
            "Records": [
                {"EventSource": "aws:sns", "Sns": {"Message": "not valid json"}},
            ]
        }

        payloads = parse_sns_event(event)

        assert len(payloads) == 1
        assert payloads[0]["message"] == "not valid json"

    def test_empty_records(self):
        event = {"Records": []}
        payloads = parse_sns_event(event)
        assert len(payloads) == 0


class TestLambdaHandler:
    @patch("handler.container")
    def test_successful_processing(self, mock_container, sample_sns_event, mock_lambda_context):
        mock_router = MagicMock()
        mock_router.route.return_value = {"telegram": True, "slack": True}
        mock_container.router.return_value = mock_router

        response = lambda_handler(sample_sns_event, mock_lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["message"] == "Processed"
        assert len(body["results"]) == 1
        mock_router.route.assert_called_once()

    @patch("handler.container")
    def test_partial_failure(self, mock_container, sample_sns_event, mock_lambda_context):
        mock_router = MagicMock()
        mock_router.route.return_value = {"telegram": True, "slack": False}
        mock_container.router.return_value = mock_router

        response = lambda_handler(sample_sns_event, mock_lambda_context)

        assert response["statusCode"] == 207
        body = json.loads(response["body"])
        assert body["message"] == "Partially processed"

    @patch("handler.container")
    def test_no_payloads(self, mock_container, mock_lambda_context):
        event = {"Records": []}

        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["message"] == "No payloads to process"

    @patch("handler.container")
    def test_exception_handling(self, mock_container, sample_sns_event, mock_lambda_context):
        mock_container.router.side_effect = Exception("Config error")

        response = lambda_handler(sample_sns_event, mock_lambda_context)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "error" in body
