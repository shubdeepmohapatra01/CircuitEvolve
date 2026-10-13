#!/usr/bin/env bash
# Verify the frozen verifier stack is unchanged (run before every evolution campaign).
cd "$(dirname "$0")/.." && shasum -a 256 -c FROZEN.sha256
