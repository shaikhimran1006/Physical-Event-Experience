# Default Dockerfile for Cloud Build/Cloud Run source deployments.
# Mirrors Dockerfile.monolith so builds succeed when Dockerfile path is not customized.

FROM node:20-alpine AS dashboard-build

WORKDIR /src/dashboard

COPY dashboard/package*.json ./
RUN npm ci

COPY dashboard/ ./
RUN npm run build

FROM node:20-alpine AS fan-build

WORKDIR /src/fan-app

COPY fan-app/package*.json ./
RUN npm ci

COPY fan-app/ ./
RUN npm run build -- --base /fan-ui/

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY backend/ /app/backend/
COPY deployment/monolith/nginx.conf /etc/nginx/conf.d/default.conf
COPY deployment/monolith/start.sh /usr/local/bin/start.sh

COPY --from=dashboard-build /src/dashboard/dist /usr/share/nginx/html
COPY --from=fan-build /src/fan-app/dist /usr/share/nginx/html/fan-ui

RUN chmod +x /usr/local/bin/start.sh

EXPOSE 8080

CMD ["/usr/local/bin/start.sh"]
