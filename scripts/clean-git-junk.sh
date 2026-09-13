#!/bin/sh
# This repo lives on an exFAT volume, which has no native support for Unix
# extended attributes. macOS shadows every file written there with a "._*"
# AppleDouble sidecar, and those sidecars can end up inside .git and corrupt
# it (bad pack index, invalid refs). Strip them after every commit.
find "$(git rev-parse --git-dir)" -name '._*' -delete 2>/dev/null
exit 0
