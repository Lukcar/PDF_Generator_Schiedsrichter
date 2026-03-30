#!/usr/bin/env sh
set -eu

mkdir -p /data

exec python /opt/schiedsrichter_browser/app/app.py
