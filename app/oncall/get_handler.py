from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from oncall.service import get_current_oncall

logger = Logger()
tracer = Tracer()


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    Get current on-call person for escalation level.

    Input:
      - level: Escalation level (1, 2, 3)

    Output:
      - phone: Phone number
      - name: Person name
      - found: Whether on-call was found
    """
    level = event.get("level", 1)
    logger.info("Getting on-call", level=level)

    oncall = get_current_oncall(level)

    if oncall:
        return {
            "phone": oncall["phone"],
            "name": oncall["name"],
            "found": True,
        }
    else:
        return {
            "phone": None,
            "name": None,
            "found": False,
        }
