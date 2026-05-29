#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAG="${1:-harness-exec:0.1.0}"
docker build -f "${ROOT}/docker/harness-exec/Dockerfile" -t "${TAG}" "${ROOT}"
echo "Built ${TAG}"
