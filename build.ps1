param(
  [string]$Tag = "latest",
  [string]$Registry = "mfmfahy",
  [string]$Platforms = "linux/amd64,linux/arm64",
  [switch]$Push
)

$ErrorActionPreference = "Stop"

# Ensure buildx is available
$builder = "multiarch-builder"
$existing = docker buildx ls --format "{{.Name}}" | Where-Object { $_ -eq $builder }
if (-not $existing) {
  Write-Host "Creating buildx builder: $builder" -ForegroundColor Cyan
  docker buildx create --name $builder --driver docker-container --bootstrap
}

docker buildx use $builder

# Build using Bake (variables passed to docker-bake.hcl)
$env:TAG = $Tag
$env:REGISTRY = $Registry
$env:PLATFORMS = $Platforms

$action = if ($Push) { "--push" } else { "--load" }

if ($Push) {
  Write-Host "Building & pushing multi-arch images ($Platforms)..." -ForegroundColor Cyan
} else {
  Write-Host "Building for local platform..." -ForegroundColor Cyan
  Write-Host "NOTE: --load only supports single platform. Use '-Push' for multi-arch." -ForegroundColor Yellow
}

docker buildx bake -f docker-bake.hcl $action

Write-Host "Done!" -ForegroundColor Green
