# Production Hardening Checklist (Cloud Run)

Use this checklist after functional deployment is working. It focuses on safe rollout, runtime observability, and incident operations.

Automation shortcuts:

- Staged canary script: `deployment/run_canary_release.ps1`
- Monitoring policy templates: `deployment/monitoring/README.md`

## 1. Release Readiness Gates

Run all gates before creating a production candidate revision.

```powershell
# Backend
Set-Location backend
pytest

# Dashboard
Set-Location ..\dashboard
npm ci
npm run lint
npm run test -- --run

# Fan app
Set-Location ..\fan-app
npm ci
npm run lint
npm run test -- --run
```

Operational config gate (backend):

- `USE_GCP` set correctly for target environment
- `CORS_ORIGINS` locked to deployed frontend origins
- `WRITE_API_KEY` set (or `WRITE_JWT_SECRET` + roles configured)
- `WS_AUTH_REQUIRED=true` for production
- `WRITE_RATE_LIMIT_PER_MINUTE` tuned for expected write traffic

## 2. Staged Rollout (Canary) on Cloud Run

Deploy backend revision with no traffic, then ramp traffic in stages.

Single-command sequence (quality gates + no-traffic deploy + optional staged promotion):

```powershell
Set-Location deployment
.\run_canary_release.ps1 `
  -ProjectId "your-gcp-project-id" `
  -Image "us-central1-docker.pkg.dev/your-gcp-project-id/stadium-os/backend:release-2026-04-12" `
  -RunQualityGates

# Optional staged traffic shift after identifying revisions
# .\run_canary_release.ps1 -ProjectId "your-gcp-project-id" -Image "..." -ShiftTraffic -OldRevision "stadium-backend-00014-def" -NewRevision "stadium-backend-00015-abc"
```

```powershell
$PROJECT_ID = "your-gcp-project-id"
$REGION = "us-central1"
$BACKEND_SERVICE = "stadium-backend"
$IMAGE = "$REGION-docker.pkg.dev/$PROJECT_ID/stadium-os/backend:release-2026-04-12"

gcloud config set project $PROJECT_ID

gcloud run deploy $BACKEND_SERVICE `
  --image $IMAGE `
  --region $REGION `
  --no-traffic `
  --allow-unauthenticated `
  --set-env-vars "USE_GCP=true,WS_AUTH_REQUIRED=true"
```

Get current and latest revisions:

```powershell
gcloud run revisions list --service $BACKEND_SERVICE --region $REGION
```

Example staged traffic progression:

```powershell
# 5% canary
# Replace REV_NEW and REV_OLD with real revision names
$REV_NEW = "stadium-backend-00015-abc"
$REV_OLD = "stadium-backend-00014-def"

gcloud run services update-traffic $BACKEND_SERVICE `
  --region $REGION `
  --to-revisions "$REV_NEW=5,$REV_OLD=95"

# Then 25%, 50%, 100% if metrics stay healthy
gcloud run services update-traffic $BACKEND_SERVICE --region $REGION --to-revisions "$REV_NEW=25,$REV_OLD=75"
gcloud run services update-traffic $BACKEND_SERVICE --region $REGION --to-revisions "$REV_NEW=50,$REV_OLD=50"
gcloud run services update-traffic $BACKEND_SERVICE --region $REGION --to-revisions "$REV_NEW=100"
```

Immediate rollback:

```powershell
gcloud run services update-traffic $BACKEND_SERVICE `
  --region $REGION `
  --to-revisions "$REV_OLD=100"
```

## 3. Runtime Metrics Sink and Log Retention

### 3.1 Create log-based metrics

Create metrics for API error rate and websocket broadcast failures.

```powershell
$PROJECT_ID = "your-gcp-project-id"

gcloud logging metrics create stadium_backend_5xx_count `
  --project $PROJECT_ID `
  --description "Count of backend HTTP 5xx responses" `
  --log-filter "resource.type=cloud_run_revision AND resource.labels.service_name=stadium-backend AND httpRequest.status>=500"

gcloud logging metrics create stadium_ws_broadcast_errors `
  --project $PROJECT_ID `
  --description "Count of websocket broadcast exceptions" `
  --log-filter "resource.type=cloud_run_revision AND resource.labels.service_name=stadium-backend AND textPayload:\"WebSocket broadcast error\""

gcloud logging metrics create stadium_container_instance_restarts `
  --project $PROJECT_ID `
  --description "Count of container exit/restart style system log events" `
  --log-filter "resource.type=cloud_run_revision AND resource.labels.service_name=stadium-backend AND log_name:\"run.googleapis.com%2Fvarlog%2Fsystem\" AND textPayload:\"Container called exit\""
```

### 3.2 Create a runtime log sink to BigQuery

```powershell
$REGION = "us-central1"
$DATASET = "stadium_runtime_logs"

bq --location=US mk -d "$PROJECT_ID:$DATASET"

gcloud logging sinks create stadium-runtime-sink `
  "bigquery.googleapis.com/projects/$PROJECT_ID/datasets/$DATASET" `
  --project $PROJECT_ID `
  --log-filter "resource.type=cloud_run_revision"
```

After sink creation, grant the sink writer identity BigQuery Data Editor on the dataset.

```powershell
gcloud logging sinks describe stadium-runtime-sink --project $PROJECT_ID
# Copy writerIdentity value, then grant it access to the dataset in IAM.
```

## 4. Alerting Baseline (Set in Cloud Monitoring)

Create alert policies for:

- `stadium_backend_5xx_count` above baseline for 5 minutes
- P95 latency regression (Cloud Run request latency)
- Container instance restart spikes
- `stadium_ws_broadcast_errors` sustained non-zero for 10 minutes

Route notifications to on-call channel and incident email.

Template pack and render/apply helper: `deployment/monitoring/README.md`.

## 5. Production Runbook

### 5.1 Fast health triage

```powershell
$BACKEND_URL = "https://your-backend-url"
Invoke-RestMethod "$BACKEND_URL/health/live"
Invoke-RestMethod "$BACKEND_URL/health/ready"
Invoke-RestMethod "$BACKEND_URL/health"
```

If `/health/live` is healthy but `/health/ready` is failing, treat as dependency readiness failure.

### 5.2 Incident log query

```powershell
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=stadium-backend" `
  --project $PROJECT_ID `
  --freshness="30m" `
  --limit=200
```

### 5.3 Incident response actions

- `P1` high 5xx or widespread websocket failures:
  - Roll back traffic to last good revision immediately.
  - Freeze new rollout promotion.
  - Capture logs and revision diff.
- `P2` elevated latency only:
  - Hold traffic at current canary percentage.
  - Raise min instances for warm capacity.
  - Recheck in 10 minutes before next promotion.

### 5.4 Capacity hotfix

```powershell
gcloud run services update stadium-backend `
  --region $REGION `
  --min-instances 2 `
  --max-instances 50
```

### 5.5 Post-incident closure

- Record timeline, trigger, mitigation, and customer impact.
- Add one test/alert per escaped failure mode.
- Update this runbook with exact fix steps.
