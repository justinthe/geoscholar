CL := tofu -chdir=infra/cluster-local
PL := tofu -chdir=infra/platform
TAG ?= latest
export KUBECONFIG := $(CURDIR)/infra/cluster-local/.state/kubeconfig

.PHONY: up down deploy pf
up:
	$(CL) init && $(CL) apply -auto-approve
	$(PL) init && $(PL) apply -auto-approve

# platform destroy is best-effort (empty state / dead cluster must not block cluster delete)
down:
	-$(PL) init && $(PL) destroy -auto-approve
	$(CL) init && $(CL) destroy -auto-approve

deploy:
	$(PL) apply -auto-approve -var api_image_tag=$(TAG) -var ui_image_tag=$(TAG)

pf:
	kubectl -n geoscholar port-forward svc/geoscholar-geoscholar-api 18000:8000 & \
	kubectl -n geoscholar port-forward svc/geoscholar-geoscholar-ui 18501:8501 & \
	kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 13000:80 & \
	wait

SCENARIO ?= baseline
RUN_TAG ?= $(shell date +%Y-%m-%dT%H%M%S)

.PHONY: load load-headline
load:
	docker run --rm --user $(shell id -u):$(shell id -g) --network host -v "$(CURDIR)/load:/scripts:ro" -v "$(CURDIR)/eval:/eval:ro" -v "$(CURDIR)/eval/results:/results" -e BASE_URL=http://localhost:18000 -e SCENARIO=$(SCENARIO) -e RUN_TAG=$(RUN_TAG) grafana/k6 run /scripts/query.js

load-headline:
	$(MAKE) load SCENARIO=headline
