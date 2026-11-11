{{- define "geoscholar.name" -}}{{ .Chart.Name }}{{- end }}
{{- define "geoscholar.fullname" -}}{{ .Release.Name }}-{{ .Chart.Name }}{{- end }}
{{- define "geoscholar.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}
{{- define "geoscholar.selector" -}}
app.kubernetes.io/name: {{ .root.Chart.Name }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end }}
{{/* Ollama URL the API uses */}}
{{- define "geoscholar.ollamaUrl" -}}
{{- if .Values.ollama.enabled }}http://{{ include "geoscholar.fullname" . }}-ollama:11434{{ else }}{{ .Values.ollama.url }}{{ end -}}
{{- end }}
