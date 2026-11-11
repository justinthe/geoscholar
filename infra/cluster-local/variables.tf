variable "cluster_name" {
  type    = string
  default = "geoscholar"
}

variable "network" {
  type        = string
  default     = "geoscholar_default"
  description = "Existing docker compose network the k3d cluster joins."
}
