import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import boto3
from aws_lambda_powertools import Logger

logger = Logger()

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("ALERTS_TABLE_NAME", "alerts"))

# KST timezone
KST = timezone(timedelta(hours=9))


def get_current_oncall(level: int = 1) -> Optional[dict]:
    """
    Get current on-call person for the given escalation level.

    Priority:
    1. Override for today's date
    2. Time-based schedule (weekday/weekend, business/after hours)
    3. Weekly rotation roster
    """
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    hour = now.hour
    is_weekend = now.weekday() >= 5  # Saturday=5, Sunday=6

    # 1. Check override for today
    override = _get_override(today, level)
    if override:
        logger.info("Using override schedule", date=today, level=level)
        return override

    # 2. Check time-based schedule
    schedule = _get_time_schedule(is_weekend, hour, level)
    if schedule:
        logger.info("Using time-based schedule", is_weekend=is_weekend, hour=hour, level=level)
        return schedule

    # 3. Fall back to weekly rotation
    roster = _get_rotation_roster(level)
    if roster:
        logger.info("Using weekly rotation", level=level)
        return roster

    logger.warning("No on-call found", level=level)
    return None


def _get_override(date: str, level: int) -> Optional[dict]:
    """Get override for specific date and level."""
    try:
        response = table.get_item(
            Key={
                "PK": f"ONCALL#override",
                "SK": f"DATE#{date}#LEVEL#{level}",
            }
        )
        item = response.get("Item")
        if item and item.get("active", True):
            return {"phone": item["phone"], "name": item.get("name", "Unknown")}
    except Exception as e:
        logger.exception("Failed to get override")
    return None


def _get_time_schedule(is_weekend: bool, hour: int, level: int) -> Optional[dict]:
    """Get time-based schedule."""
    try:
        if is_weekend:
            sk = f"WEEKEND#LEVEL#{level}"
        elif 9 <= hour < 18:
            sk = f"WEEKDAY#BUSINESS#LEVEL#{level}"
        else:
            sk = f"WEEKDAY#NIGHT#LEVEL#{level}"

        response = table.get_item(
            Key={
                "PK": "ONCALL#schedule",
                "SK": sk,
            }
        )
        item = response.get("Item")
        if item and item.get("active", True):
            return {"phone": item["phone"], "name": item.get("name", "Unknown")}
    except Exception as e:
        logger.exception("Failed to get time schedule")
    return None


def _get_rotation_roster(level: int) -> Optional[dict]:
    """Get current person from weekly rotation roster."""
    try:
        # Get current rotation index
        rotation_response = table.get_item(
            Key={
                "PK": "ONCALL#rotation",
                "SK": "CURRENT",
            }
        )
        rotation = rotation_response.get("Item", {})
        current_index = rotation.get("current_index", 0)

        # Get roster members
        roster_response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
            ExpressionAttributeValues={
                ":pk": "ONCALL#roster",
                ":sk": "MEMBER#",
            },
        )
        members = sorted(roster_response.get("Items", []), key=lambda x: x.get("order", 0))

        if not members:
            return None

        # Get current member based on rotation
        current_member = members[current_index % len(members)]

        # For escalation levels > 1, get next members in rotation
        if level > 1:
            member_index = (current_index + level - 1) % len(members)
            current_member = members[member_index]

        return {"phone": current_member["phone"], "name": current_member.get("name", "Unknown")}

    except Exception as e:
        logger.exception("Failed to get rotation roster")
    return None


def rotate_oncall() -> dict:
    """Rotate to next person in roster. Called weekly by EventBridge."""
    try:
        # Get current rotation
        response = table.get_item(
            Key={
                "PK": "ONCALL#rotation",
                "SK": "CURRENT",
            }
        )
        rotation = response.get("Item", {})
        current_index = rotation.get("current_index", 0)

        # Get roster size
        roster_response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
            ExpressionAttributeValues={
                ":pk": "ONCALL#roster",
                ":sk": "MEMBER#",
            },
            Select="COUNT",
        )
        roster_size = roster_response.get("Count", 1)

        # Update to next index
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
