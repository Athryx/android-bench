#!/bin/sh

# updates dependencies from git
uv lock \
  -P kbench -P kexploit-agent -P kexploit-utils \
  -P ksandbox -P cuttle-cli -P cuttle-types

uv sync --locked
