# Cloud Monitoring Alert Templates

These templates align with the production hardening metrics from deployment/PRODUCTION_HARDENING_CHECKLIST.md.

## Included Templates

- alert-backend-5xx.json
- alert-websocket-errors.json
- alert-latency-p95.json
- alert-instance-restarts.json

## 1) Create Required Log-Based Metrics

```powershell
$PROJECT_ID = "your-gcp-project-id"
$BACKEND_SERVICE = "stadium-backend"

gcloud logging metrics create stadium_backend_5xx_count `
  --project $PROJECT_ID `
  --description "Count of backend HTTP 5xx responses" `
  --log-filter "resource.type=cloud_run_revision AND resource.labels.service_name=$BACKEND_SERVICE AND httpRequest.status>=500"

gcloud logging metrics create stadium_ws_broadcast_errors `
  --project $PROJECT_ID `
  --description "Count of websocket broadcast exceptions" `
  --log-filter "resource.type=cloud_run_revision AND resource.labels.service_name=$BACKEND_SERVICE AND textPayload:\"WebSocket broadcast error\""

gcloud logging metrics create stadium_container_instance_restarts `
  --project $PROJECT_ID `
  --description "Count of container exit/restart style system log events" `
  --log-filter "resource.type=cloud_run_revision AND resource.labels.service_name=$BACKEND_SERVICE AND log_name:\"run.googleapis.com%2Fvarlog%2Fsystem\" AND textPayload:\"Container called exit\""
```

## 2) Render Policy JSON With Environment Values

```powershell
$PROJECT_ID = "your-gcp-project-id"
$NOTIFICATION_CHANNEL = "projects/$PROJECT_ID/notificationChannels/1234567890123456789"

Set-Location deployment/monitoring
.\apply_alert_policies.ps1 -ProjectId $PROJECT_ID -BackendService "stadium-backend" -NotificationChannel $NOTIFICATION_CHANNEL
```

Rendered files are written to deployment/monitoring/rendered.

## 3) Create Alert Policies In Cloud Monitoring

```powershell
$PROJECT_ID = "your-gcp-project-id"
$NOTIFICATION_CHANNEL = "projects/$PROJECT_ID/notificationChannels/1234567890123456789"

Set-Location deployment/monitoring
.\apply_alert_policies.ps1 -ProjectId $PROJECT_ID -BackendService "stadium-backend" -NotificationChannel $NOTIFICATION_CHANNEL -CreatePolicies
```

## Notes

- Thresholds are templates and should be tuned with production traffic baselines.
- If your channel strategy differs by severity, duplicate templates and adjust notificationChannels per policy.
- For strict canary gating, require no active incidents on these policies before moving 25% -> 50% -> 100%.
