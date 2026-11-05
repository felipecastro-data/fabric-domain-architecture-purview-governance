# One-command local workflow. `make check` runs what the `ci` gate runs plus every tool's dry run (live, read-only).
# Needs uv, terraform, tflint and az login (Fabric administrator); see README "Run it yourself".
.DEFAULT_GOAL := help
UV ?= uv
TF ?= terraform
STACKS := governance domains
TOOLS := workspace-domains tenant-settings domain-contributors onelake-roles data-product-governance
# Import the package from the tree, not through the editable install's .pth file: macOS can flag that file hidden
# (iCloud-synced folders), and Python skips hidden .pth files.
export PYTHONPATH := $(CURDIR)/src

.PHONY: help setup lint fmt test tf-check dry-run check plan apply charts

help: ## List the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  make %-9s %s\n", $$1, $$2}'

setup: ## Install Python 3.12 and the locked dependencies
	$(UV) sync --locked --group dev

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

dry-run: setup ## Every tool as a dry run against the live tenant (exits 1 on drift)
	@for s in $(STACKS); do $(TF) -chdir=infra/terraform/$$s init -input=false >/dev/null || exit 1; done
	@for t in $(TOOLS); do echo "== $$t"; $(UV) run $$t || exit 1; done

check: test tf-check dry-run ## Everything: lint, tests, Terraform static checks, live dry runs

plan: ## terraform plan for both stacks (governance first)
	@for s in $(STACKS); do echo "== $$s"; $(TF) -chdir=infra/terraform/$$s init -input=false >/dev/null && $(TF) -chdir=infra/terraform/$$s plan -lock-timeout=5m || exit 1; done

apply: setup ## Apply governance, then domains, then the tools (same order as CI)
	$(TF) -chdir=infra/terraform/governance init -input=false
	$(TF) -chdir=infra/terraform/governance apply -lock-timeout=5m
	$(TF) -chdir=infra/terraform/domains init -input=false
	$(TF) -chdir=infra/terraform/domains apply -lock-timeout=5m
	$(UV) run tenant-settings --apply
	$(UV) run domain-contributors --apply
	$(UV) run onelake-roles --apply
	$(UV) run data-product-governance --apply
	$(UV) run workspace-domains

charts: setup ## Re-render the README charts from Terraform outputs and OneLake
	$(UV) run --extra onelake --extra charts mesh-charts --out docs/charts
