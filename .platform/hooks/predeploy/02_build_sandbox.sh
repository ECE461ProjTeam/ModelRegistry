#!/bin/bash
set -e
# Build the sandbox Docker image
sudo docker build -t js-sandbox-image -f Dockerfile.js-sandbox .