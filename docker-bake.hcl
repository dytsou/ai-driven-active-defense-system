// Build all app images: docker buildx bake
// With Compose:     COMPOSE_BAKE=true docker compose up -d --build

variable "TAG" {
  default = "latest"
}

variable "REGISTRY" {
  default = ""
}

group "default" {
  targets = ["app", "keystroke-ml"]
}

group "compose" {
  targets = ["app", "keystroke-ml"]
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

target "keystroke-ml" {
  context    = "services/keystroke-ml"
  dockerfile = "Keystroke_Dockerfile"
  tags       = image_tag("keystroke-ml")
}
