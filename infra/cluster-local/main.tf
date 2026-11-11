terraform {
  required_version = ">= 1.6"
}

# No k3d provider exists, so shell out. Joins the compose network so pods
# resolve host-compose Ollama as `ollama`. No host ports published
# (use kubectl port-forward; see `make pf`).
resource "terraform_data" "cluster" {
  input = { name = var.cluster_name, kubeconfig = "${path.module}/.state/kubeconfig" }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      set -euo pipefail
      if ! docker network inspect ${var.network} >/dev/null 2>&1; then
        echo "ERROR: docker network ${var.network} not found. Run: docker compose up -d ollama qdrant" >&2
        exit 1
      fi
      k3d cluster create ${var.cluster_name} --network ${var.network} --servers 1 --agents 0 --wait
      mkdir -p ${path.module}/.state
      k3d kubeconfig get ${var.cluster_name} > ${path.module}/.state/kubeconfig
      chmod 600 ${path.module}/.state/kubeconfig
    EOT
  }

  provisioner "local-exec" {
    when        = destroy
    interpreter = ["/bin/bash", "-c"]
    command     = "k3d cluster delete ${self.input.name} || echo 'cluster ${self.input.name} already gone'; rm -f ${self.input.kubeconfig}"
  }
}
