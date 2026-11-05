"""Fabric data mesh tools: settings the Terraform provider cannot manage, and the compliance checks.

Every tool reads its desired state from `terraform output` (except tenant_settings), runs as a dry run by default,
exits 1 on drift and changes the tenant only with ``--apply``.
"""
