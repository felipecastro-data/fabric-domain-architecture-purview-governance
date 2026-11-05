# ADR 0005 — Keep a committed plan file in git history (accepted)

- **Status:** Accepted
- **Date:** 2026-11-05

## Context

Commit `4e54e06` added `infra/terraform/governance/tfplan`; `8437ed2` removed it and added `tfplan` to `.gitignore`.
The blob is still in history. A saved plan is a zip with the configuration and a state snapshot. A scan of the blob
found **no credentials**: it holds the tenant ID, Entra object IDs of groups and the admin user, Fabric domain IDs and
label IDs.

Those identifiers are not secrets. Using any of them needs an authenticated identity in the tenant, and several are
already visible in public workflow logs and the README screenshots.

## Options

| | Option | For | Against |
|---|---|---|---|
| A | **Purge** with `git filter-repo --path infra/terraform/governance/tfplan --invert-paths` and force-push | Removes the identifiers from history | Rewrites every later commit: merged PR links and commit SHAs break, `main` protection must be lifted, and forks and clones keep the blob anyway |
| B | **Accept** and prevent a repeat | No history rewrite; honest record | Identifiers stay in history |

## Decision

**Option B.** The blob holds identifiers, not credentials, and rewriting a protected, public `main` costs more than it
protects. A repeat is prevented by `.gitignore` (`tfplan`, `*.tfplan`, `*.tfstate*`, `local.auto.tfvars`) and by the
`local.auto.tfvars.example` files, which show the required inputs with empty values.

## Consequences

- If a credential is ever found in history, rotate it first, then purge (Option A) regardless of the cost.
- **Revisit when:** the repository moves to a tenant where tenant and object IDs are treated as confidential.
