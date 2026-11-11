output "kubeconfig_path" {
  value      = abspath("${path.module}/.state/kubeconfig")
  depends_on = [terraform_data.cluster]
}
