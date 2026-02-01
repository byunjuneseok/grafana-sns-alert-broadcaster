import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import boto3
from aws_lambda_powertools import Logger

logger = Logger()

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("ALERTS_TABLE_NAME", "alerts"))

KST = timezone(timedelta(hours=9))


def get_current_oncall(level: int = 1) -> Optional[dict]:
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")

    override = _get_override(today, level)
    if override:
        logger.info("Using override", date=today, level=level)
        return override

    roster = _get_rotation_roster(level)
    if roster:
        logger.info("Using rotation", level=level)
        return roster

    logger.warning("No on-call found", level=level)
    return None


def _get_override(date: str, level: int) -> Optional[dict]:
    try:
        response = table.get_item(
            Key={"PK": "ONCALL#override", "SK": f"DATE#{date}#LEVEL#{level}"}
        )
        item = response.get("Item")
        if item and item.get("active", True):
            return {"phone": item["phone"], "name": item.get("name", "Unknown")}
    except Exception:
        logger.exception("Failed to get override")
    return None


def _get_rotation_roster(level: int) -> Optional[dict]:
    try:
        rotation_response = table.get_item(
            Key={"PK": "ONCALL#rotation", "SK": "CURRENT"}
        )
        rotation = rotation_response.get("Item", {})
        current_index = rotation.get("current_index", 0)

        roster_response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
            ExpressionAttributeValues={":pk": "ONCALL#roster", ":sk": "MEMBER#"},
        )
        members = sorted(roster_response.get("Items", []), key=lambda x: x.get("order", 0))

        if not members:
            return None

        member_index = (current_index + level - 1) % len(members)
        current_member = members[member_index]

        return {"phone": current_member["phone"], "name": current_member.get("name", "Unknown")}

    except Exception:
        logger.exception("Failed to get rotation roster")
    return None


def rotate_oncall() -> dict:
    try:
        response = table.get_item(Key={"PK": "ONCALL#rotation", "SK": "CURRENT"})
        rotation = response.get("Item", {})
        current_index = rotation.get("current_index", 0)

        roster_response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
            ExpressionAttributeValues={":pk": "ONCALL#roster", ":sk": "MEMBER#"},
            Select="COUNT",
        )
        roster_size = roster_response.get("Count", 1)

        new_index = (current_index + 1) % roster_size

        table.put_item(
            Item={
                "PK": "ONCALL#rotation",
                "SK": "CURRENT",
                "current_index": new_index,
                "rotated_at": datetime.now(KST).isoformat(),
            }
        )

        logger.info("Rotation updated", old_index=current_index, new_index=new_index)
        return {"old_index": current_index, "new_index": new_index}

    except Exception as e:
        logger.exception("Failed to rotate")
        return {"error": str(e)}
