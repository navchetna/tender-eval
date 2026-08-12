{{- define "pdf-pipeline.namespace" -}}
{{- .Values.namespaceOverride | default .Release.Namespace }}
{{- end }}
