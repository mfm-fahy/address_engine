variable "TAG" {
  default = "latest"
}

variable "REGISTRY" {
  default = "mfmfahy"
}

variable "PLATFORMS" {
  default = "linux/amd64,linux/arm64"
}

group "default" {
  targets = ["backend", "frontend"]
}

target "backend" {
  dockerfile = "Dockerfile"
  context = "server"
  tags = ["${REGISTRY}/addressing-backend:${TAG}"]
  platforms = split(",", PLATFORMS)
  cache-from = ["type=gha"]
  cache-to = ["type=gha,mode=max"]
}

target "frontend" {
  dockerfile = "Dockerfile"
  context = "client"
  tags = ["${REGISTRY}/addressing-frontend:${TAG}"]
  platforms = split(",", PLATFORMS)
  cache-from = ["type=gha"]
  cache-to = ["type=gha,mode=max"]
}
