#!/usr/bin/env bash
HARNESS_CWD="$(pwd)"
cd "$(dirname "$0")"
HARNESS_CWD="$HARNESS_CWD" .venv/bin/python main.py
