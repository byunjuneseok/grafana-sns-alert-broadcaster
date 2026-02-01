#!/usr/bin/env python
import argparse

import boto3


def seed_oncall(table_name: str):
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    items = [
        {
            "PK": "ONCALL#roster",
            "SK": "MEMBER#1",
            "name": "홍길동",
            "phone": "+821012345678",
            "order": 1,
        },
        {
            "PK": "ONCALL#roster",
            "SK": "MEMBER#2",
            "name": "김철수",
            "phone": "+821087654321",
            "order": 2,
        },
        {
            "PK": "ONCALL#roster",
            "SK": "MEMBER#3",
            "name": "이영희",
            "phone": "+821011112222",
            "order": 3,
        },
        {
            "PK": "ONCALL#rotation",
            "SK": "CURRENT",
            "current_index": 0,
        },
        {
            "PK": "ONCALL#schedule",
            "SK": "WEEKDAY#BUSINESS#LEVEL#1",
            "name": "주간 당번",
            "phone": "+821012345678",
            "active": True,
        },
        {
            "PK": "ONCALL#schedule",
            "SK": "WEEKDAY#NIGHT#LEVEL#1",
            "name": "야간 당번",
            "phone": "+821087654321",
            "active": True,
        },
        {
            "PK": "ONCALL#schedule",
            "SK": "WEEKEND#LEVEL#1",
            "name": "주말 당번",
            "phone": "+821011112222",
            "active": True,
        },
    ]

    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)
            print(f"Added: {item['PK']} / {item['SK']}")

    print("Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True, help="DynamoDB table name")
    args = parser.parse_args()
    seed_oncall(args.table)
