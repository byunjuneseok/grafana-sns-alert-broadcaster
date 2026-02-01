from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from oncall.service import rotate_oncall

logger = Logger()
tracer = Tracer()


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Weekly rotation handler. Triggered by EventBridge."""
    logger.info("Starting weekly rotation")
    result = rotate_oncall()
    logger.info("Rotation complete", result=result)
    return result
