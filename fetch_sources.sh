#!/bin/sh
# Downloads the six arXiv papers used as source pages.
set -e
mkdir -p sources
for id in 1706.03762 2005.11401 1810.04805 2303.08774 2106.09685 1512.03385; do
  curl -sL -o "sources/$id.pdf" "https://arxiv.org/pdf/$id"
done
ls sources
