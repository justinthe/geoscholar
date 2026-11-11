terraform {
  required_version = ">= 1.6"
  required_providers {
    helm       = { source = "hashicorp/helm", version = "~> 3.0" }
    kubernetes = { source = "hashicorp/kubernetes", version = "~> 2.30" }
  }
}

provider "kubernetes" {
  config_path = var.kubeconfig_path
}

provider "helm" {
  kubernetes = {
    config_path = var.kubeconfig_path
  }
}

resource "kubernetes_namespace" "geoscholar" {
  metadata {
    name = var.namespace
  }
}

# Chart 1.20.0 ships app v1.20.0. Persistence (PVC) is on by default.
resource "helm_release" "qdrant" {
  name       = "qdrant"
  namespace  = kubernetes_namespace.geoscholar.metadata[0].name
  repository = "https://qdrant.github.io/qdrant-helm"
  chart      = "qdrant"
  version    = "1.20.0"
  wait       = true

  values = [yamlencode({
    image       = { tag = "v1.20.0" }
    persistence = { size = "10Gi" }
  })]
}

# Grafana admin password: managed by the chart (it generates the
# kube-prometheus-stack-grafana Secret). Nothing is set in code or state here.
# Read it with: kubectl -n monitoring get secret kube-prometheus-stack-grafana \
#   -o jsonpath='{.data.admin-password}' | base64 -d
resource "helm_release" "kube_prometheus_stack" {
  name             = "kube-prometheus-stack"
  namespace        = "monitoring"
  create_namespace = true
  repository       = "https://prometheus-community.github.io/helm-charts"
  chart            = "kube-prometheus-stack"
  version          = "93.2.0"
  wait             = true
  timeout          = 900

  values = [yamlencode({
    alertmanager = { enabled = false }
    grafana = {
      sidecar = { dashboards = { enabled = true, label = "grafana_dashboard" } }
    }
    prometheus = {
      prometheusSpec = {
        serviceMonitorSelectorNilUsesHelmValues = false
        podMonitorSelectorNilUsesHelmValues     = false
      }
    }
  })]
}

# /ingest stays disabled (chart default GEOSCHOLAR_ENABLE_INGEST=false).
resource "helm_release" "geoscholar" {
  name      = "geoscholar"
  namespace = kubernetes_namespace.geoscholar.metadata[0].name
  chart     = "${path.module}/../../charts/geoscholar"
  wait      = true
  timeout   = 600

  values = [yamlencode({
    api            = { image = { repository = var.api_image_repository, tag = var.api_image_tag } }
    ui             = { image = { repository = var.ui_image_repository, tag = var.ui_image_tag } }
    ollama         = { enabled = false, url = var.ollama_url }
    config         = { GEOSCHOLAR_LLM = var.llm_model }
    serviceMonitor = { enabled = true, labels = { release = "kube-prometheus-stack" } }
    dashboard      = { enabled = true }
  })]

  depends_on = [helm_release.kube_prometheus_stack, helm_release.qdrant]
}
