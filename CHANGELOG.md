# Changelog

All notable changes to this project are documented in this file.

## 2026-04-12

### Added

- Modular backend package structure under backend/app with routers, services, schemas, websocket manager, and core utilities.
- Health split endpoints: /health, /health/live, /health/ready.
- Optional JWT token issuance endpoint: /auth/token.
- Production hardening playbook at deployment/PRODUCTION_HARDENING_CHECKLIST.md.
- One-command canary rollout script at deployment/run_canary_release.ps1.
- Cloud Monitoring alert policy templates and application script under deployment/monitoring.
- Expanded backend test suites for core modules, security flows, websocket behavior, and platform service orchestration.

### Changed

- Backend startup now uses lifespan-based initialization with readiness state.
- Backend request handling now includes structured request logging and security response headers.
- Mutating endpoints now support optional API key and JWT role-based access policies.
- WebSocket endpoints now support auth policy enforcement and improved error branch handling.
- Pytest configuration now enforces coverage gate and warning suppression for known third-party noise.
- CI backend test job now runs pytest with coverage policy from project config.

### Improved

- Backend total coverage raised above gate and validated at 97.71%.
- WebSocket router file coverage raised to 100% via additional edge-case tests.
- Dashboard and fan-app polling paths hardened with timeout handling, visibility-aware polling, and safer refresh behavior.

### Operational Notes

- This release introduces staged rollout and rollback procedures for Cloud Run.
- Monitoring setup now includes templates for 5xx spikes, websocket errors, latency regression, and container restart spikes.
