#!/usr/bin/env bash
set -euo pipefail

mkdir -p /data

exec python /opt/schiedsrichter_browser/app/app.py
