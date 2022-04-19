#!/bin/bash

set -eo pipefail

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd "$SCRIPT_DIR"
S3DIR="s3://public.mckelvie.org"

aws s3 cp ../vpyapp.py "$S3DIR/vpyapp.py"
