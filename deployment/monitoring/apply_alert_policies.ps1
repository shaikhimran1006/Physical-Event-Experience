param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,

    [string]$BackendService = "stadium-backend",

    [Parameter(Mandatory = $true)]
    [string]$NotificationChannel,

    [switch]$CreatePolicies
)

$ErrorActionPreference = "Stop"

$templateDir = $PSScriptRoot
$renderedDir = Join-Path $templateDir "rendered"
New-Item -ItemType Directory -Path $renderedDir -Force | Out-Null

Get-ChildItem -Path $templateDir -Filter "*.json" | ForEach-Object {
    $templatePath = $_.FullName
    $templateText = Get-Content -Raw -Path $templatePath

    $rendered = $templateText.Replace("__PROJECT_ID__", $ProjectId)
    $rendered = $rendered.Replace("__BACKEND_SERVICE__", $BackendService)
    $rendered = $rendered.Replace("__NOTIFICATION_CHANNEL__", $NotificationChannel)

    $outputPath = Join-Path $renderedDir $_.Name
    Set-Content -Path $outputPath -Value $rendered -NoNewline
    Write-Host "Rendered: $outputPath"

    if ($CreatePolicies) {
        gcloud alpha monitoring policies create --policy-from-file=$outputPath --project=$ProjectId
        Write-Host "Created policy from: $outputPath"
    }
}

Write-Host "Done. Rendered policy files are in $renderedDir"
