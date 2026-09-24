# Rahti Weather - Docker Compose Deployment (VPS)

This branch runs the same rahti-weather application as the OpenShift deployment on `main`, but as a plain Docker Compose stack for a VPS. The Python application code is unchanged — only the orchestration differs (`docker-compose.yml` replaces the four OpenShift deployment YAMLs).

## Components

| Service | Replaces | Runs |
| --- | --- | --- |
| `postgresql` | `postgresql-deployment.yaml` | PostgreSQL 15.3 (Bitnami image), data in a named volume |
| `kafka` | `kafka-deployment.yaml` | Kafka 4.3.1 broker (KRaft mode, single node, PLAINTEXT) |
| `web` | `app-deployment.yaml` | Flask web UI plus the producer (COMPONENT=web runs both) |
| `consumer` | `consumer-deployment.yaml` | Kafka consumer inserting into PostgreSQL |

## Prerequisites

- Docker with the Compose plugin (`docker compose version`)
- Outbound internet access (to pull images and reach the Open-Meteo API)

## Quick Start

```bash
# Optional: override credentials and behaviour (see .env.example)
cp .env.example .env

# Build the app image and start the whole stack
docker compose up -d --build
```

The web UI is available at `http://<VPS-IP>:8080` (override with `WEB_PORT` in `.env`).

## Verify the Data Flow

```bash
# All services healthy?
docker compose ps

# Producer: should show "Sent to Kafka" lines
docker compose logs web | grep "Sent to Kafka" | tail

# Consumer: should show "Received message" / "Inserted" pairs
docker compose logs consumer | grep -E "Received message|Inserted" | tail

# Query the database directly to confirm rows are landing
docker compose exec postgresql env PGPASSWORD=$POSTGRESQL_PASSWORD \
  /opt/bitnami/postgresql/bin/psql -U weatheruser -d weatherdb \
  -c "SELECT location, temp, wind, time FROM weather ORDER BY id DESC LIMIT 5"
```

> Tip: with the default schedule the producer polls every 15 minutes, so a fresh stack may take up to 15 minutes before the first `Sent to Kafka` line appears.

## Fast Testing the Data Flow

Set the producer to poll every minute in `.env` (or export it before `docker compose up`):

```bash
POLL_MINUTES_UTC=0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59
```

Apply the change with:

```bash
docker compose up -d web
```

> Note: Open-Meteo updates its current-weather data every 15 minutes. Polling faster will show the data flowing through the pipeline more frequently, but the weather values themselves will repeat until the API updates.

## Differences from the OpenShift Deployment

- **Persistence**: PostgreSQL uses a named Docker volume (`postgresql-data`), so data survives `docker compose down`. On Rahti the database uses `emptyDir` and is wiped when the pod is recreated. (Kafka log dirs are still ephemeral, matching Rahti — the `weather` topic is auto-created on first produce.)
- **Health checks**: Docker healthchecks mirror the OpenShift liveness probes (web `/health` on 8080, consumer `/health` on 8082, `pg_isready` for PostgreSQL, TCP check for Kafka). Failed healthchecks mark the container unhealthy but do not restart it; `restart: unless-stopped` covers crashes and reboots.
- **Startup ordering**: `depends_on` with `condition: service_healthy` makes web and consumer wait for PostgreSQL and Kafka to be healthy before starting, which the OpenShift deployment handles with its bootstrap retry loops.
- **No route/TLS**: the web UI is served plain HTTP on port 8080. For anything exposed to the internet, put a reverse proxy (Caddy, nginx, Traefik) in front for HTTPS, or restrict access with a firewall.
- **Credentials**: set via `.env` (git-ignored). Do not commit real credentials.

## Updating

After changing application code, rebuild and restart the app services:

```bash
docker compose up -d --build web consumer
```

## Cleanup

> **Warning:** `docker compose down -v` permanently deletes the database volume and all weather data. Run it only when you want to tear the stack down completely.

```bash
# Stop and remove containers (keep data)
docker compose down

# Stop and remove containers AND the database volume
docker compose down -v
```
