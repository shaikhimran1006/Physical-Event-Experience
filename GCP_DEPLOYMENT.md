# GCP Deployment Guide (Stadium OS Copilot)

This project now supports deployment to Google Cloud Run with runtime-configurable frontend endpoints.

## Keyless vs Key File (Important)

- Local-like mode (no keys): set `USE_GCP=false` and backend runs with in-memory/local fallbacks.
- Cloud Run keyless mode: set `USE_GCP=true` and use a Cloud Run service account with IAM roles.
- You do NOT need a JSON key file on Cloud Run when IAM is configured.
- `GOOGLE_APPLICATION_CREDENTIALS` is only needed if you explicitly use a local service-account key file.

## Architecture

- `backend` -> Cloud Run service (FastAPI + WebSocket)
- `dashboard` -> Cloud Run service (React static app on Nginx)
- `fan-app` -> Cloud Run service (React static app on Nginx)

## 1. Prerequisites

- A GCP project with billing enabled
- `gcloud` CLI installed and authenticated
- Cloud Build and Artifact Registry permissions in your project

## 2. Configure Variables (PowerShell)

```powershell
$PROJECT_ID = "your-gcp-project-id"
$REGION = "us-central1"
$REPO = "stadium-os"

$BACKEND_SERVICE = "stadium-backend"
$DASHBOARD_SERVICE = "stadium-dashboard"
$FAN_SERVICE = "stadium-fan"

gcloud config set project $PROJECT_ID
```

## 3. Enable Required APIs

```powershell
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

If you want full managed data integrations (`USE_GCP=true`), also enable:

```powershell
gcloud services enable firestore.googleapis.com pubsub.googleapis.com bigquery.googleapis.com
```

## 4. Create Artifact Registry (One Time)

```powershell
gcloud artifacts repositories create $REPO `
  --repository-format=docker `
  --location=$REGION `
  --description="Stadium OS images"

gcloud auth configure-docker "$REGION-docker.pkg.dev"
```

## 5. Build and Push Images

```powershell
gcloud builds submit backend --tag "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/backend:latest"
gcloud builds submit dashboard --tag "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/dashboard:latest"
gcloud builds submit fan-app --tag "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/fan-app:latest"
```

## 6. Deploy Backend First

### Quick Demo Mode (no Firestore/PubSub/BigQuery required)

```powershell
gcloud run deploy $BACKEND_SERVICE `
  --image "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/backend:latest" `
  --region $REGION `
  --allow-unauthenticated `
  --port 8080 `
  --set-env-vars "USE_GCP=false,CORS_ORIGINS=*"
```

Get backend URL:

```powershell
$BACKEND_URL = gcloud run services describe $BACKEND_SERVICE --region $REGION --format "value(status.url)"
$BACKEND_WS_URL = $BACKEND_URL -replace '^https', 'wss' -replace '^http', 'ws'
```

## 7. Deploy Frontends

```powershell
gcloud run deploy $DASHBOARD_SERVICE `
  --image "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/dashboard:latest" `
  --region $REGION `
  --allow-unauthenticated `
  --port 8080 `
  --set-env-vars "API_URL=$BACKEND_URL,WS_URL=$BACKEND_WS_URL"

gcloud run deploy $FAN_SERVICE `
  --image "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/fan-app:latest" `
  --region $REGION `
  --allow-unauthenticated `
  --port 8080 `
  --set-env-vars "API_URL=$BACKEND_URL"
```

## 8. Lock Down CORS (Recommended)

After frontend deployment, get URLs and update backend CORS:

```powershell
$DASHBOARD_URL = gcloud run services describe $DASHBOARD_SERVICE --region $REGION --format "value(status.url)"
$FAN_URL = gcloud run services describe $FAN_SERVICE --region $REGION --format "value(status.url)"

gcloud run services update $BACKEND_SERVICE `
  --region $REGION `
  --update-env-vars "CORS_ORIGINS=$DASHBOARD_URL,$FAN_URL"
```

## 9. Full GCP Integration Mode (Optional)

Use this if you want Firestore/PubSub/BigQuery persistence and analytics.

### 9.1 Create resources

```powershell
# Firestore (one-time, choose region carefully)
gcloud firestore databases create --location=$REGION --type=firestore-native

# Pub/Sub topics
gcloud pubsub topics create crowd_events
gcloud pubsub topics create queue_events
gcloud pubsub topics create interventions
gcloud pubsub topics create user_notifications

# BigQuery dataset
bq --location=US mk -d "$PROJECT_ID:stadium_os_analytics"
```

### 9.2 Service account and IAM

```powershell
$RUN_SA = "stadium-runner@$PROJECT_ID.iam.gserviceaccount.com"

gcloud iam service-accounts create stadium-runner --display-name "Stadium OS Cloud Run SA"

gcloud projects add-iam-policy-binding $PROJECT_ID --member "serviceAccount:$RUN_SA" --role "roles/datastore.user"
gcloud projects add-iam-policy-binding $PROJECT_ID --member "serviceAccount:$RUN_SA" --role "roles/pubsub.publisher"
gcloud projects add-iam-policy-binding $PROJECT_ID --member "serviceAccount:$RUN_SA" --role "roles/bigquery.dataEditor"
gcloud projects add-iam-policy-binding $PROJECT_ID --member "serviceAccount:$RUN_SA" --role "roles/bigquery.jobUser"
```

### 9.3 Reconfigure backend

```powershell
gcloud run services update $BACKEND_SERVICE `
  --region $REGION `
  --service-account $RUN_SA `
  --update-env-vars "USE_GCP=true,GCP_PROJECT_ID=$PROJECT_ID,BQ_DATASET=stadium_os_analytics,CORS_ORIGINS=$DASHBOARD_URL,$FAN_URL"
```

## 11. Troubleshooting Missing Key Errors

If the app fails due to credential/key issues:

1. For local/demo behavior, run backend with `USE_GCP=false`.
2. For Cloud Run managed integrations, keep `USE_GCP=true`, attach the Cloud Run service account, and grant IAM roles.
3. Avoid setting `GOOGLE_APPLICATION_CREDENTIALS` on Cloud Run unless you intentionally mount a key file.
4. Check health endpoint to confirm mode:

```powershell
Invoke-RestMethod "$BACKEND_URL/health"
```

Look at:

- `gcp_requested`
- `gcp_enabled`
- `gcp_services`

## 10. Verify Deployment

```powershell
Invoke-RestMethod "$BACKEND_URL/health"
```

Open frontend URLs:

- Dashboard URL from `stadium-dashboard`
- Fan app URL from `stadium-fan`

## Runtime Config Notes

- Backend CORS is controlled by `CORS_ORIGINS` (comma-separated, or `*`)
- Dashboard runtime config env vars:
  - `API_URL`
  - `WS_URL` (optional, auto-derived from `API_URL` if omitted)
- Fan app runtime config env var:
  - `API_URL`
