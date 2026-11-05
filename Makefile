# One-command local workflow. `make check` runs what the `ci` gate runs plus every tool's dry run (live, read-only).
# ENV=dev|prod (default prod) selects the domains environment: `make plan ENV=dev`, `make apply ENV=dev`.
# Needs uv, terraform, tflint and az login (Fabric administrator); see README "Run it yourself".
.DEFAULT_GOAL := help
UV ?= uv
TF ?= terraform
STACKS := governance domains
ENV ?= prod
DOMAINS_WORKSPACE := $(if $(filter prod,$(ENV)),fabric-mesh-domains,fabric-mesh-domains-$(ENV))
# Domains commands run in the HCP workspace of $(ENV); the tools pick it from MESH_ENV
DOMAINS_TF := TF_WORKSPACE=$(DOMAINS_WORKSPACE) TF_VAR_environment=$(ENV) $(TF) -chdir=infra/terraform/domains
export MESH_ENV := $(ENV)
TENANT_TOOLS := tenant-settings domain-contributors
TOOLS := workspace-domains tenant-settings domain-contributors onelake-roles data-product-governance data-contracts semantic-model
# Import the package from the tree, not through the editable install's .pth file: macOS can flag that file hidden
# (iCloud-synced folders), and Python skips hidden .pth files.
export PYTHONPATH := $(CURDIR)/src

.PHONY: help setup lint fmt test tf-check dry-run freshness check plan apply charts

help: ## List the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  make %-9s %s\n", $$1, $$2}'

setup: ## Install Python 3.12 and the locked dependencies
	$(UV) sync --locked --group dev --extra onelake

lint: setup ## Ruff lint and format check
	$(UV) run ruff check .
	$(UV) run ruff format --check .

fmt: setup ## Format Python and Terraform
	$(UV) run ruff format .
	$(UV) run ruff check --fix .
	$(TF) fmt -recursive infra/terraform

test: lint ## Unit tests (fixtures only, no network)
	$(UV) run pytest

tf-check: ## terraform fmt, validate and tflint for both stacks (no backend)
	$(TF) fmt -check -recursive -diff infra/terraform
	@for s in $(STACKS); do \
	  echo "== $$s"; \
	  $(TF) -chdir=infra/terraform/$$s init -backend=false -input=false >/dev/null && \
	  $(TF) -chdir=infra/terraform/$$s validate -no-color || exit 1; \
	  if command -v tflint >/dev/null; then (cd infra/terraform/$$s && tflint --init >/dev/null && tflint --recursive --format compact) || exit 1; \
	  else echo "tflint not installed: skipped (CI runs it)"; fi; \
	done

dry-run: setup ## Every tool as a dry run against the live tenant, in ENV (exits 1 on drift)
	@$(TF) -chdir=infra/terraform/governance init -input=false >/dev/null
	@$(DOMAINS_TF) init -input=false >/dev/null
	@for t in $(TOOLS); do echo "== $$t"; $(UV) run $$t || exit 1; done

freshness: setup ## Each data contract's latency SLA (newest Delta write per product)
	@$(DOMAINS_TF) init -input=false >/dev/null
	$(UV) run data-freshness

check: test tf-check dry-run ## Everything: lint, tests, Terraform static checks, live dry runs

plan: ## terraform plan: governance, then domains in ENV
	$(TF) -chdir=infra/terraform/governance init -input=false >/dev/null
	$(TF) -chdir=infra/terraform/governance plan -lock-timeout=5m
	$(DOMAINS_TF) init -input=false >/dev/null
	$(DOMAINS_TF) plan -lock-timeout=5m

apply: setup ## Apply governance, then domains in ENV, then the tools (same order as CI)
	$(TF) -chdir=infra/terraform/governance init -input=false
	$(TF) -chdir=infra/terraform/governance apply -lock-timeout=5m
	$(DOMAINS_TF) init -input=false
	$(DOMAINS_TF) apply -lock-timeout=5m
	$(if $(filter prod,$(ENV)),for t in $(TENANT_TOOLS); do $(UV) run $$t --apply || exit 1; done,)
	$(UV) run onelake-roles --apply
	$(UV) run data-product-governance --apply
	$(UV) run workspace-domains
	$(UV) run semantic-model --refresh

charts: setup ## Re-render the README charts from Terraform outputs and OneLake
	$(UV) run --extra onelake --extra charts mesh-charts --out docs/charts
