<#
.SYNOPSIS
  Creates (or updates) the Purview sensitivity labels used by the Fabric data mesh and publishes them in a label policy.
  Idempotent: re-running converges labels and policy to this file.

.DESCRIPTION
  Sensitivity labels are not managed by the Terraform fabric provider, so they live here as code
  (Security & Compliance PowerShell). Labels are classification only (no encryption): protected labels
  restrict sharing and export in Fabric, which is out of scope for this project.

  Writes infra/terraform/governance/labels.auto.tfvars.json (gitignored) with the label IDs so Terraform can set
  each domain's default label. New or changed labels take up to 24 hours to reach Fabric.

.EXAMPLE
  pwsh tools/purview/labels.ps1 -UserPrincipalName new_user_fabric@felipe9393icloud384.onmicrosoft.com
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)] [string] $UserPrincipalName,
  [string] $PolicyName = 'Fabric Data Mesh'
)

$ErrorActionPreference = 'Stop'

# Ordered from least to most sensitive: creation order sets label priority.
$labels = @(
  @{ Name = 'mesh-public';              DisplayName = 'Public';              Tooltip = 'Data that can be shared publicly (e.g. open weather data).' }
  @{ Name = 'mesh-general';             DisplayName = 'General';             Tooltip = 'Internal data, not for public release.' }
  @{ Name = 'mesh-confidential';        DisplayName = 'Confidential';        Tooltip = 'Business data with ride-level detail; share only with approved consumers.' }
  @{ Name = 'mesh-highly-confidential'; DisplayName = 'Highly Confidential'; Tooltip = 'Personal or regulated data; restricted to named owners.' }
)

Import-Module ExchangeOnlineManagement
Connect-IPPSSession -UserPrincipalName $UserPrincipalName -ShowBanner:$false

try {
  foreach ($l in $labels) {
    $existing = Get-Label -Identity $l.Name -ErrorAction SilentlyContinue
    if ($existing) {
      Set-Label -Identity $l.Name -DisplayName $l.DisplayName -Tooltip $l.Tooltip | Out-Null
      Write-Host "updated  $($l.DisplayName)"
    } else {
      New-Label -Name $l.Name -DisplayName $l.DisplayName -Tooltip $l.Tooltip -ContentType 'File, Email' | Out-Null
      Write-Host "created  $($l.DisplayName)"
    }
  }

  $names = $labels | ForEach-Object { $_.Name }
  $policy = Get-LabelPolicy -Identity $PolicyName -ErrorAction SilentlyContinue
  if ($policy) {
    Set-LabelPolicy -Identity $PolicyName -AddLabels $names | Out-Null
    Write-Host "updated  policy '$PolicyName'"
  } else {
    New-LabelPolicy -Name $PolicyName -Labels $names -ExchangeLocation All `
      -Comment 'Publishes the Fabric data mesh labels to all users (managed by tools/purview/labels.ps1)' | Out-Null
    Write-Host "created  policy '$PolicyName' (published to all users)"
  }

  # Label IDs for Terraform (domain default labels)
  $ids = [ordered]@{}
  foreach ($l in $labels) { $ids[$l.DisplayName] = (Get-Label -Identity $l.Name).ImmutableId.ToString() }
  $out = Join-Path $PSScriptRoot '../../infra/terraform/governance/labels.auto.tfvars.json'
  @{ sensitivity_label_ids = $ids } | ConvertTo-Json | Set-Content -Path $out -Encoding utf8
  Write-Host "wrote    $out"
  $ids | Format-Table -AutoSize
}
finally {
  Disconnect-ExchangeOnline -Confirm:$false
}
