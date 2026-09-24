# Rahti Weather - Docker Deployment

Weather monitoring pipeline that fetches data from the Open-Meteo API, processes it through Kafka, stores it in PostgreSQL, and displays it via a Flask web interface.

This branch runs the application as a Docker Compose stack, suited for a VPS or local machine. The OpenShift (Rahti) deployment lives on the `main` branch — the application code is identical on both branches, only the orchestration differs.

## Data Flow

```
Open-Meteo API → Producer → [Kafka Topic] → Consumer → PostgreSQL → Web Interface
```

The producer runs inside the web container (`COMPONENT=web` starts both, see `entrypoint.sh`) and polls Open-Meteo for each configured location (Oulu, Lapinaho) at fixed minutes past the hour. The consumer subscribes to the Kafka topic and inserts each message into PostgreSQL.

## Services

| Service | Runs | Port |
| --- | --- | --- |
| `web` | Flask web UI plus the producer (built from this repo) | 8080 internal, published on host 8088 (default) |
| `consumer` | Kafka consumer inserting into PostgreSQL (built from this repo) | 8082 (internal, health checks) |
| `kafka` | Kafka 4.3.1 broker, KRaft mode, single node, PLAINTEXT | 9092 (internal) |
| `postgresql` | PostgreSQL 15.3 (Bitnami image), data in a named volume | 5432 (internal) |

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

The web UI is available at `http://localhost:8088` (on a VPS: `http://<VPS-IP>:8088`). Override the host port with `WEB_PORT` in `.env`. The container itself always listens on 8080 internally — `WEB_PORT` only changes the published host port, so it can never conflict with anything on your machine.

> `postgresql` and `kafka` must report healthy before `web` and `consumer` start (`depends_on` with `condition: service_healthy`), so the first start takes a minute or two.

## Configuration

All configuration is optional — copy `.env.example` to `.env` and adjust. Values can also be exported in the shell before `docker compose up`.

| Variable | Default | Description |
| --- | --- | --- |
| `POSTGRESQL_USERNAME` | `weatheruser` | Database user (shared by postgresql, web and consumer) |
| `POSTGRESQL_PASSWORD` | `weatherpass` | Database password. **Change this on any internet-facing VPS** |
| `POSTGRESQL_DATABASE` | `weatherdb` | Database name |
| `WEB_PORT` | `8088` | Host port for the web UI (8080 is often already taken in dev environments) |
| `STATUS_PAGE_ENABLED` | `false` | Set `true` to enable the `/status` page and its link on the home page |
| `POLL_MINUTES_UTC` | `1,16,31,46` | Minutes past the hour (UTC) when the producer polls Open-Meteo |
| `DB_MAX_SIZE_MB` | `256` | When the `weather` table exceeds this size (MB), the consumer deletes the oldest rows automatically |
| `KAFKA_HEAP_OPTS` | `-Xmx512m -Xms256m` | Kafka JVM heap. Lower on a small VPS |

After changing `.env`, re-create the affected services:

```bash
docker compose up -d
```

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

## Health Checks

Each service has a Docker healthcheck mirroring the OpenShift liveness probes:

- `web`: HTTP GET `/health` on 8080 (checks database connectivity)
- `consumer`: HTTP GET `/health` on 8082 (checks Kafka and database)
- `postgresql`: `pg_isready`
- `kafka`: TCP check on 9092

A failed healthcheck marks the container `unhealthy` but does not restart it; `restart: unless-stopped` covers crashes and VPS reboots. Check current health with `docker compose ps`.

If `STATUS_PAGE_ENABLED=true`, the web UI also has a `/status` page showing the health of web, producer and consumer on one page (auto-refreshes every 10 seconds).

## Persistence

PostgreSQL data lives in the `postgresql-data` named volume and survives `docker compose down` and VPS reboots. Kafka log directories are ephemeral (matching the OpenShift deployment) — the `weather` topic is auto-created on first produce, so no action is needed after a Kafka restart.

As a safety valve, the consumer checks the size of the `weather` table after every insert: if it exceeds `DB_MAX_SIZE_MB` (default 256 MB), the oldest rows are deleted until the table is back under the limit, and the freed space is reclaimed with `VACUUM`. The normal data flow only inserts ~200 rows/day (~20 MB/year), so with sane settings the cleanup never triggers — it is there to keep the volume bounded if something starts inserting junk. Each cleanup is logged as a `Table cleanup:` line in `docker compose logs consumer`.

## Updating

After changing application code, rebuild and restart the app services:

```bash
docker compose up -d --build web consumer
```

## Production Notes

- The web UI is served plain HTTP on the published host port (8088 by default). For anything exposed to the internet, put a reverse proxy (Caddy, nginx, Traefik) in front for HTTPS, or restrict access with a firewall.
- Change `POSTGRESQL_PASSWORD` from the default. Credentials are set via `.env`, which is git-ignored — do not commit real credentials.
- On a small VPS (1-2 GB RAM), lower `KAFKA_HEAP_OPTS` if Kafka struggles for memory; it is the largest consumer in the stack.

## Cleanup

> **Warning:** `docker compose down -v` permanently deletes the database volume and all weather data. Run it only when you want to tear the stack down completely.

```bash
# Stop and remove containers (keep data)
docker compose down

# Stop and remove containers AND the database volume
docker compose down -v
```
