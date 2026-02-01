#!/bin/bash
set -e

uv export --no-hashes --no-dev --no-editable -o app/requirements.txt
