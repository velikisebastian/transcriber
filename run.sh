#!/bin/sh
cd "$(dirname "$(readlink -f "$0")")" && exec .venv/bin/python transcriber.py "$@"
