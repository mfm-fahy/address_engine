#!/usr/bin/env bash
set -euo pipefail

TAG="${1:-latest}"
REGISTRY="${2:-mfmfahy}"
PLATFORMS="linux/amd64,linux/arm64"
PUSH="${3:-}"

BUILDER="multiarch-builder"
if ! docker buildx ls --format "{{.Name}}" | grep -q "$BUILDER"; then
  echo "Creating buildx builder: $BUILDER"
  docker buildx create --name "$BUILDER" --driver docker-container --bootstrap
fi

docker buildx use "$BUILDER"

export TAG REGISTRY PLATFORMS

if [ "$PUSH" = "push" ]; then
  echo "Building & pushing multi-arch images ($PLATFORMS)..."
  docker buildx bake -f docker-bake.hcl --push
else
  echo "Building for local platform..."
  docker buildx bake -f docker-bake.hcl --load
  echo "NOTE: --load only supports single platform. Use: ./build.sh latest mfmfahy push"
fi

echo "Done!"
