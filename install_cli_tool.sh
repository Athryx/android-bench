#!/bin/sh

cd "$(dirname $0)"

uv tool install --reinstall --editable .
