param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,

    [Parameter(Mandatory = $true)]
    [string]$Image,

    [string]$Region = "us-central1",
    [string]$BackendService = "stadium-backend",
    [string]$EnvVars = "USE_GCP=true,WS_AUTH_REQUIRED=true",

    [switch]$RunQualityGates,
    [switch]$ShiftTraffic,

    [string]$OldRevision,
    [string]$NewRevision
)

$ErrorActionPreference = "Stop"

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action
    )

    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Action
}

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot

try {
    if ($RunQualityGates) {
        Invoke-Step -Name "Backend tests" -Action {
            Set-Location backend
            pytest
            Set-Location ..
        }

        Invoke-Step -Name "Dashboard lint and tests" -Action {
            Set-Location dashboard
            npm ci
            npm run lint
            npm run test -- --run
            Set-Location ..
        }

        Invoke-Step -Name "Fan app lint and tests" -Action {
            Set-Location fan-app
            npm ci
            npm run lint
            npm run test -- --run
            Set-Location ..
        }
    }

    Invoke-Step -Name "Set active GCP project" -Action {
        gcloud config set project $ProjectId
    }

    Invoke-Step -Name "Deploy backend revision with no traffic" -Action {
        gcloud run deploy $BackendService `
            --image $Image `
            --region $Region `
            --no-traffic `
            --allow-unauthenticated `
            --set-env-vars $EnvVars
    }

    Invoke-Step -Name "List backend revisions" -Action {
        gcloud run revisions list --service $BackendService --region $Region
    }

    if ($ShiftTraffic) {
        if ([string]::IsNullOrWhiteSpace($OldRevision) -or [string]::IsNullOrWhiteSpace($NewRevision)) {
            throw "When -ShiftTraffic is set, both -OldRevision and -NewRevision are required."
        }

        $stages = @(
            @{ New = 5; Old = 95 },
            @{ New = 25; Old = 75 },
            @{ New = 50; Old = 50 },
            @{ New = 100; Old = 0 }
        )

        foreach ($stage in $stages) {
            $newPct = $stage.New
            $oldPct = $stage.Old

            if ($newPct -lt 100) {
                Invoke-Step -Name "Shift traffic: new=$newPct old=$oldPct" -Action {
                    gcloud run services update-traffic $BackendService `
                        --region $Region `
                        --to-revisions "$NewRevision=$newPct,$OldRevision=$oldPct"
                }

                $continue = Read-Host "Press Enter to continue to next stage, or type stop to halt rollout"
                if ($continue -eq "stop") {
                    Write-Host "Rollout paused by operator." -ForegroundColor Yellow
                    break
                }
            }
            else {
                Invoke-Step -Name "Shift traffic: new=100" -Action {
                    gcloud run services update-traffic $BackendService `
                        --region $Region `
                        --to-revisions "$NewRevision=100"
                }
            }
        }
    }

    Write-Host "Canary release sequence complete." -ForegroundColor Green
}
finally {
    Pop-Location
}
