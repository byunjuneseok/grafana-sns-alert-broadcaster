#!/bin/bash
set -e

STAGE=${1:-dev}

echo "Exporting dependencies..."
./omit_deps.sh

echo "Building SAM application..."
sam build -c -p -u

echo "Deploying to ${STAGE}..."
sam deploy --config-env ${STAGE}
