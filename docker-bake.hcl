// Build all app images: docker buildx bake
// With Compose:     COMPOSE_BAKE=true docker compose up -d --build

variable "TAG" {
  default = "latest"
}

variable "REGISTRY" {
  default = ""
}

group "default" {
  targets = ["app", "mock-ml"]
}

group "compose" {
  targets = ["app", "mock-ml"]
}

function "image_tag" {
  params = [name]
  result = notequal("", REGISTRY) ? ["${REGISTRY}/active-defense-${name}:${TAG}"] : ["active-defense/${name}:${TAG}"]
}

target "app" {
  context  = "."
  dockerfile = "Dockerfile"
  tags     = image_tag("app")
}

target "mock-ml" {
  context    = "services/mock-ml"
  dockerfile = "Dockerfile"
  tags       = image_tag("mock-ml")
}
