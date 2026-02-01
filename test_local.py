#!/usr/bin/env python
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

from dotenv import load_dotenv

load_dotenv()
os.environ["POWERTOOLS_TRACE_DISABLED"] = "true"

os.chdir(Path(__file__).parent / "app")
sys.path.insert(0, ".")

from handler import lambda_handler

ctx = MagicMock()
ctx.function_name = "test"
ctx.memory_limit_in_mb = 128
ctx.invoked_function_arn = "arn:aws:lambda:ap-northeast-2:123456789:function:test"
ctx.aws_request_id = "test-id"

with open("../events/test_event.json") as f:
    event = json.load(f)

result = lambda_handler(event, ctx)
print(json.dumps(result, indent=2))
