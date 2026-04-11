# Stadium OS

Real-time crowd intelligence for live events.

Stadium OS helps operations teams and fans make faster decisions using live venue state, queue predictions, intervention recommendations, and guided routing.

## What Is Included

- Operations Dashboard for command-center monitoring
- Fan App for gate, concession, and exit guidance
- FastAPI backend for ingestion, prediction, interventions, notifications, and simulation

## Repository Structure

- [backend](backend): API, services, simulation engine
- [dashboard](dashboard): React operations interface
- [fan-app](fan-app): React fan interface
- [GCP_DEPLOYMENT.md](GCP_DEPLOYMENT.md): deployment instructions

## Tech Stack

- Backend: FastAPI, Uvicorn, Python
- Frontend: React, Vite
- Deployment: Docker, Nginx, Google Cloud Run
- Optional managed services: Firestore, Pub/Sub, BigQuery

## Quick Start (Local)

Prerequisites:

- Python 3.10+
- Node.js 18+
- npm

1. Start backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:USE_GCP="false"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

2. Start dashboard

```powershell
cd dashboard
npm install
npm run dev
```

3. Start fan app

```powershell
cd fan-app
npm install
npm run dev -- --port 5174
```

4. Open URLs

- Dashboard: http://localhost:5173
- Fan App: http://localhost:5174
- Backend health: http://localhost:8000/health

## Key API Endpoints

- GET /health
- POST /simulation/start
- GET /simulation/status
- GET /state/{venue_id}
- GET /interventions/{venue_id}
- GET /fan/{venue_id}/best-gate
- GET /fan/{venue_id}/best-concession
- GET /fan/{venue_id}/exit-guidance

Implementation reference: [backend/main.py](backend/main.py)

## Deployment

Use [GCP_DEPLOYMENT.md](GCP_DEPLOYMENT.md).

Supported options:

- Multi-service: backend + dashboard + fan app
- Single-service: monolith container
