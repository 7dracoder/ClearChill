#!/usr/bin/env bash
# Render.com build script

set -o errexit

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
