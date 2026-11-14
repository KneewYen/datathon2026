#!/usr/bin/env bash
# Upload starter CSVs to S3 (private bucket).
set -euo pipefail
: "${S3_BUCKET:?set S3_BUCKET}"
aws s3 sync "$(dirname "$0")/../data" "s3://$S3_BUCKET/starter/" --exclude "*" --include "*.csv"
