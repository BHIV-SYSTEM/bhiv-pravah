# Pravah Local and Production Deployment Guide

This guide outlines the operations and structure of the Pravah deployment infrastructure. It includes local developer commands, production VM layouts, and CI/CD parameters.

---

## 📑 Table of Contents
1. [Architecture Overview](#1-architecture-overview)
2. [Local Service Port Reference](#2-local-service-port-reference)
3. [Local Development Lifecycle (Scripts)](#3-local-development-lifecycle-scripts)
4. [Production CI/CD VM Deployment](#4-production-cicd-vm-deployment)
5. [Monitoring Integration](#5-monitoring-integration)

---

## 1. Architecture Overview

Pravah is a multi-agent system composed of:
- **Redis (Event Bus)**: The shared messaging backbone.
- **Control Plane API**: Flask/Gunicorn-driven orchestrator managing decisions and system registries.
- **Decision Brain API**: FastAPI/Uvicorn-driven policy and reinforcement learning ingestion layer.
- **Observer Server**: Passive health-probing dashboard checking active systems in real-time.
- **Deploy Workers**: Three parallel workers executing deployment tasks.
- **Queue/Health Monitors**: Status analysis engines.
- **Prometheus Scraper**: Metrics collection and scraper engine.

---

## 2. Local Service Port Reference

| Service | Host Port | Internal Port | Health Check Path | Description |
|---|---|---|---|---|
| **Control Plane** | `7000` | `7000` | `/api/health` | Agent orchestration API |
| **Decision Brain** | `8010` | `8000` | `/health` | Policy / telemetry endpoint |
| **Observer** | `8600` | `8600` | `/health` | Passive health dashboard |
| **Redis** | `6380` | `6380` | *TCP Ping* | System event bus |
| **Prometheus** | `9093` | `9090` | `/-/healthy` | Metrics aggregator |

---

## 3. Local Development Lifecycle (Scripts)

Run these scripts from the system folder root (`pravah-bhiv/`):

### Start / Build Stack
```bash
bash deployment/deploy.sh
```
This builds local images and boots all core services in detached background mode.

### Stop / Clean Stack
```bash
bash deployment/stop.sh
```
This stops and destroys running containers while retaining volume data.

### Restart Stack
```bash
bash deployment/restart.sh
```
Restarts all containers in the stack and prints their updated runtime statuses.

### View Logs
```bash
# Tail all container logs
bash deployment/logs.sh

# Tail a specific service (e.g., control-plane)
bash deployment/logs.sh control-plane
```

### Run Health Checks
```bash
bash deployment/healthcheck.sh
```
Performs docker process validation and runs HTTP health probes against all running endpoints.

---

## 4. Production CI/CD VM Deployment

### Workflow Configuration
Production VM deployment is driven by the GitHub Actions pipeline defined in `.github/workflows/cicd.yml`. It performs:
1. Multi-stage Docker build from `pravah-bhiv/backend/Dockerfile` and pushes to Docker Hub with Git short SHA tag.
2. Tars deployment files (`docker-compose.production.template.yml` and environment settings) and transfers them to VM via SSH.
3. Automatically substitutes `IMG_TAG` inside `docker-compose.production.template.yml` to generate `docker-compose.production.yml`.
4. Deploys the stack, runs 12 loops of health checks, and registers the release in `docs/RELEASE_HISTORY.md` (with backup).
5. If the deployment fails health checks, it automatically triggers a rollback to the last successful tag by parsing `RELEASE_HISTORY.md`.

### Production Environment Variables
Environment configurations reside in `backend/environments/` and the pipeline automatically maps the production secrets to the active VM `.env`.

---

## 5. Monitoring Integration

The Prometheus service runs alongside the stack, reading metrics from:
- Control Plane (`http://control-plane:7000/metrics`)
- Decision Brain (`http://decision-brain:8000/metrics`)
- Observer (`http://observer:8600/api/metrics`)
