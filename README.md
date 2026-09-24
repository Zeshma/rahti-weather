# Rahti Weather - OpenShift Deployment Guide

## Overview
This guide explains how to deploy the Rahti Weather application on OpenShift. The application provides a complete weather monitoring pipeline that fetches data from Open-Meteo API, processes it through Kafka, stores it in PostgreSQL, and displays it via a web interface.

This guide was done for Oulu University of Applied Sciences as part of Company-Oriented Product Development Project course.

## Prerequisites
- OpenShift CLI (`oc`) installed and logged in
- Access to an OpenShift project
- **PostgreSQL database instance** (can be deployed on OpenShift or external)
- **Kafka instance** (can be deployed on OpenShift or external)
- **Your own credentials** for database and Kafka (do not use hardcoded values)
- Podman or Docker for building container images (on Fedora/Linux)

> ⚠️ **IMPORTANT**: This guide uses placeholder values for sensitive information. You **MUST** replace all placeholder values with your actual credentials before deployment.

## Preparation: Set Up Your Credentials

Before deploying, you need to gather your database and Kafka connection details:

### Database Configuration
Prepare these values for your PostgreSQL database:
- `DB_HOST` - Your PostgreSQL server hostname or IP
- `DB_NAME` - Database name (e.g., "weatherdb")
- `DB_USER` - Database username
- `DB_PASSWORD` - Database password
- `DB_PORT` - Database port (typically 5432)

### Kafka Configuration
Prepare these values for your Kafka instance:
- `KAFKA_BOOTSTRAP_SERVERS` - Kafka bootstrap servers (e.g., "kafka:9092")

## Quick Setup for Testing

If you just want to test the deployment quickly, you can fill in all placeholders with a single command. This replaces the `<namespace>` placeholder with your OpenShift project name and sets default test credentials in `postgresql-deployment.yaml`:

```bash
# Set your namespace in all deployment YAMLs
NAMESPACE=$(oc project -q)
sed -i "s/<namespace>/${NAMESPACE}/g" app-deployment.yaml consumer-deployment.yaml kafka-deployment.yaml

# Set test credentials in postgresql-deployment.yaml
sed -i "s/<your-user>/weatheruser/g; s/<your-password>/weatherpass/g; s/<your-db>/weatherdb/g" postgresql-deployment.yaml
```

You can change `weatheruser`, `weatherpass`, and `weatherdb` to whatever you like. After running these commands, skip step 3 below (credentials are already set) and continue from step 4.

> Warning: these are plain-text test credentials. Do not use them in production. For production, use `oc set env` or OpenShift secrets instead of editing the YAMLs.

## Deployment Steps

### 1. Make the Kafka Image Available

The `kafka-deployment.yaml` references `image-registry.apps.2.rahti.csc.fi/<namespace>/kafka:4.3.1`. CSC publishes a maintained Kafka image at `satama.csc.fi/library/kafka:4.3.1` (publicly pullable, no auth needed). You need to get this image into your project's registry. Choose one of the options below.

#### Option A: Using Podman (Recommended for Fedora/Linux)
```bash
# Login to OpenShift registry
oc registry login

NAMESPACE=$(oc project -q)
podman pull satama.csc.fi/library/kafka:4.3.1
podman tag satama.csc.fi/library/kafka:4.3.1 image-registry.apps.2.rahti.csc.fi/${NAMESPACE}/kafka:4.3.1
podman push image-registry.apps.2.rahti.csc.fi/${NAMESPACE}/kafka:4.3.1

# Import the image into OpenShift
oc import-image kafka:4.3.1 \
  --from=image-registry.apps.2.rahti.csc.fi/${NAMESPACE}/kafka:4.3.1 \
  --confirm
```

#### Option B: Using Docker
```bash
# Login to OpenShift registry
oc registry login

NAMESPACE=$(oc project -q)
docker pull satama.csc.fi/library/kafka:4.3.1
docker tag satama.csc.fi/library/kafka:4.3.1 image-registry.apps.2.rahti.csc.fi/${NAMESPACE}/kafka:4.3.1
docker push image-registry.apps.2.rahti.csc.fi/${NAMESPACE}/kafka:4.3.1

# Import the image into OpenShift
oc import-image kafka:4.3.1 \
  --from=image-registry.apps.2.rahti.csc.fi/${NAMESPACE}/kafka:4.3.1 \
  --confirm
```

#### Option C: Using oc import-image directly (no local container runtime needed)
```bash
# Import straight from the public Satama registry into your project
oc import-image kafka:4.3.1 \
  --from=satama.csc.fi/library/kafka:4.3.1 \
  --confirm
```

The `oc import-image --confirm` command creates the image stream automatically if it does not exist yet. You can verify it with `oc get imagestream kafka`. If you ever need to create it manually first: `oc create imagestream kafka`.

Then replace `<namespace>` in `kafka-deployment.yaml` with your project name (or use `oc apply` with the in-cluster registry URL and patch the image afterward).

### 2. Deploy Infrastructure (Kafka and PostgreSQL)

Now deploy Kafka and PostgreSQL:

```bash
# Deploy Kafka
oc apply -f kafka-deployment.yaml

# Deploy PostgreSQL
oc apply -f postgresql-deployment.yaml

# Wait for pods to be ready
oc wait --for=condition=ready pod -l app=kafka --timeout=300s
oc wait --for=condition=ready pod -l app=postgresql --timeout=300s
```

### 3. Set Your Credentials

The deployment YAMLs use placeholder values for credentials (`<your-user>`, `<your-password>`, `<your-db>`). You have several options:

**Quick: Fill test credentials with one command** — replace the placeholders in `postgresql-deployment.yaml` with default test values (same as the Quick Setup for Testing above):

```bash
sed -i "s/<your-user>/weatheruser/g; s/<your-password>/weatherpass/g; s/<your-db>/weatherdb/g" postgresql-deployment.yaml
oc apply -f postgresql-deployment.yaml
oc rollout restart deployment/postgresql
```

You can change `weatheruser`, `weatherpass`, and `weatherdb` to whatever you like. These are plain-text test credentials — do not use them in production.

**Option A: Edit the YAMLs before applying** — replace the placeholders in `postgresql-deployment.yaml` with your chosen credentials, then redeploy:

```bash
# Edit postgresql-deployment.yaml and replace:
#   <your-user>    → your database username
#   <your-password> → your database password
#   <your-db>      → your database name

# Then apply the updated file
oc apply -f postgresql-deployment.yaml
oc rollout restart deployment/postgresql
```

**Option B: Set credentials via oc set env** — set them on the running PostgreSQL deployment:

```bash
oc set env deployment/postgresql \
  POSTGRESQL_USERNAME=<your-user> \
  POSTGRESQL_PASSWORD=<your-password> \
  POSTGRESQL_DATABASE=<your-db>
```

> Note: the PostgreSQL pod may crash-loop on first start with placeholder values. Set the credentials right after deploying, then roll out: `oc rollout restart deployment/postgresql`.

The app and consumer deployments fall back to the `POSTGRESQL_*` env vars automatically (see `config.py`), so if you use the same credentials everywhere you do not need to set `DB_*` explicitly. If you want different credentials on the app/consumer, set them after step 5 (the `rahti-weather` and `rahti-weather-consumer` deployments must exist first) — see the note at the end of step 5.

### 4. Build and Push Container Image

#### Option A: Using Podman (Recommended for Fedora/Linux)
```bash
# Login to OpenShift registry
oc whoami
oc registry login

# Get your project namespace
NAMESPACE=$(oc project -q)

# Build the image using Podman
podman build -t image-registry.apps.2.rahti.csc.fi/${NAMESPACE}/rahti-weather:latest .

# Push to OpenShift registry
podman push image-registry.apps.2.rahti.csc.fi/${NAMESPACE}/rahti-weather:latest

# Import the image into OpenShift
oc import-image rahti-weather:latest --from=image-registry.apps.2.rahti.csc.fi/${NAMESPACE}/rahti-weather:latest --confirm
```

#### Option B: Using Docker
```bash
# Login to OpenShift registry
oc whoami
oc registry login

# Get your project namespace
NAMESPACE=$(oc project -q)

# Build the image using Docker
docker build -t image-registry.apps.2.rahti.csc.fi/${NAMESPACE}/rahti-weather:latest .

# Push to OpenShift registry
docker push image-registry.apps.2.rahti.csc.fi/${NAMESPACE}/rahti-weather:latest

# Import the image into OpenShift
oc import-image rahti-weather:latest --from=image-registry.apps.2.rahti.csc.fi/${NAMESPACE}/rahti-weather:latest --confirm
```

The `oc import-image --confirm` command creates the image stream automatically. Verify with `oc get imagestream rahti-weather`. If you ever need to create it manually first: `oc create imagestream rahti-weather`.

#### Option C: Using OpenShift Build (Alternative)
```bash
# Create a build configuration
oc new-build python:3.10-slim --name=rahti-weather --binary

# Start the build
oc start-build rahti-weather --from-dir=. --follow
```

### 5. Deploy the Application and Consumer

The image references in `app-deployment.yaml`, `consumer-deployment.yaml`, and `kafka-deployment.yaml` contain a `<namespace>` placeholder. Replace it with your project name before applying, or patch the image after deploying:

```bash
# Replace <namespace> with your project name in all three files
NAMESPACE=$(oc project -q)
sed -i "s/<namespace>/${NAMESPACE}/g" app-deployment.yaml consumer-deployment.yaml kafka-deployment.yaml

# Deploy the web application (includes producer)
oc apply -f app-deployment.yaml

# Deploy the consumer
oc apply -f consumer-deployment.yaml

# Wait for pods to be ready
oc wait --for=condition=ready pod -l app=rahti-weather --timeout=300s
oc wait --for=condition=ready pod -l app=rahti-weather-consumer --timeout=300s
```

> Note: if you want different DB credentials on the app/consumer than the
> `POSTGRESQL_*` values set in step 3, set them now (the deployments exist
> at this point):
>
> ```bash
> oc set env deployment/rahti-weather \
>   DB_USER=<your-user> DB_PASSWORD=<your-password> DB_NAME=<your-db>
>
> oc set env deployment/rahti-weather-consumer \
>   DB_USER=<your-user> DB_PASSWORD=<your-password> DB_NAME=<your-db>
> ```

### 6. Verify Deployment

```bash
# Check pods are running
oc get pods

# Check services
oc get svc

# Check routes
oc get routes
```

### 7. Access the Application

The web interface will be available at the route URL shown in `oc get routes`.

Find yours with:
```bash
oc get route rahti-weather -o jsonpath='{.spec.host}{"\n"}'
```

### 8. Verify Data Flow

Once all components are running, verify the complete data flow.

The producer and consumer pods log a `GET /health` line on every probe (every ~10 s), which drowns out the actual data-flow messages. Filter the health-check noise out with `grep -v "GET /health"`, or grep for the specific signal strings.

```bash
# Producer: should show "Sent to Kafka" lines (one batch per 15-min poll).
# --tail must be large enough to reach past the health-check spam.
oc logs -l app=rahti-weather --tail=2000 | grep -v "GET /health" | tail -20

# Or grep only the produce events:
oc logs -l app=rahti-weather --tail=2000 | grep "Sent to Kafka" | tail -10

# Consumer: should show "Received message" followed by "Inserted" pairs.
oc logs -l app=rahti-weather-consumer --tail=2000 | grep -v "GET /health" | tail -20

# Or grep only the consume/insert events:
oc logs -l app=rahti-weather-consumer --tail=2000 | grep -E "Received message|Inserted" | tail -10

# Check the web interface
oc exec <rahti-weather-pod> -- python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8080/').read().decode()[:500])"

# Query the database directly to confirm rows are landing
oc exec deployment/rahti-weather-consumer -- python3 -c "
import psycopg2, config
conn = psycopg2.connect(**config.db_connection_kwargs())
cur = conn.cursor()
cur.execute('SELECT location, temp, wind, time FROM weather ORDER BY id DESC LIMIT 5')
for r in cur.fetchall():
    print(r)
cur.close(); conn.close()
"
```

> Tip: the producer polls every 15 minutes, so a fresh deployment may take up to 15 minutes before the first `Sent to Kafka` line appears. The consumer prints `Received message` / `Inserted` as soon as messages arrive.

### 9. Checking Health

Use these `oc` commands from your terminal to check the health of all components.

#### A. Check probe status (Kubernetes-level)

```bash
# Show pod readiness (readiness probe result)
oc get pods

# Show probe configuration for each deployment
oc describe pod -l app=rahti-weather | grep -A3 "Liveness\|Readiness"
oc describe pod -l app=rahti-weather-consumer | grep -A3 "Liveness\|Readiness"
oc describe pod -l app=kafka | grep -A3 "Liveness\|Readiness"
oc describe pod -l app=postgresql | grep -A3 "Liveness\|Readiness"

# Show recent probe failures and restarts
oc get events --sort-by='.lastTimestamp' | grep -i "probe\|unhealthy\|killing"
```

#### B. Check health endpoints directly (from inside pods)

```bash
# Web (database connectivity)
oc exec deployment/rahti-weather -- python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8080/health').read().decode())"

# Producer (Kafka producer status)
oc exec deployment/rahti-weather -- python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8081/health').read().decode())"

# Consumer (Kafka consumer + database)
oc exec deployment/rahti-weather-consumer -- python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8082/health').read().decode())"

# PostgreSQL (uses an exec probe, not HTTP — run pg_isready directly)
oc exec deployment/postgresql -- /opt/bitnami/postgresql/bin/pg_isready -U postgres
```

#### C. Check the status page (if enabled)

```bash
# From inside the pod
oc exec deployment/rahti-weather -- python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8080/status').read().decode()[:200])"

# From your browser: visit <route-url>/status
oc get route rahti-weather -o jsonpath='{.spec.host}{"\n"}'
# Then open http://<that-url>/status in a browser
```

## Application Architecture

The Rahti Weather application consists of three main components:

### 1. Web Application
- **Purpose**: Displays weather data in a user-friendly web interface
- **Port**: 8080
- **Technology**: Flask web framework

### 2. Producer
- **Purpose**: Fetches weather data from Open-Meteo API and publishes to Kafka (or directly to DB if Kafka disabled)
- **Locations**: Oulu (65.01, 25.47) and Lapinaho (65.89532, 28.30994)
- **Frequency**: Every 15 minutes, at fixed minutes past the hour (UTC): 01, 16, 31, 46. Configurable via `POLL_MINUTES_UTC` in `config.py`.
- **Port**: 8081 (health checks)
- **Technology**: Python with requests library

### 3. Consumer
- **Purpose**: Subscribes to Kafka, processes messages, and stores in PostgreSQL
- **Port**: 8082 (health checks)
- **Technology**: Kafka Consumer with PostgreSQL integration

## Data Flow

```
Open-Meteo API → Producer → [Kafka Topic] → Consumer → PostgreSQL → Web Interface
```

> A direct-DB fallback path (bypassing Kafka) exists in the code but is
> disabled (commented out) in this Kafka-mandatory deployment. See
> `producer.py` and `config.py` to re-enable it for local testing.

## Configuration

### Environment Variables

The application reads configuration from environment variables (see `config.py` for the full list and defaults). The defaults below are fallbacks in the Python code; set your own values via the deployment YAMLs or `oc set env`.

**Database:**
- `DB_HOST`: PostgreSQL host (default: `postgresql`)
- `DB_NAME`: PostgreSQL database name (default: `weatherdb`)
- `DB_USER`: PostgreSQL username (default: `weatheruser`)
- `DB_PASSWORD`: PostgreSQL password (default: `weatherpass`)
- `DB_PORT`: PostgreSQL port (default: `5432`)

> The `DB_*` vars fall back to the `POSTGRESQL_*` vars that the Bitnami PostgreSQL image sets, so if both deployments use the same credentials you may not need to set `DB_*` explicitly.

**Kafka:**
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka bootstrap servers (default: `kafka:9092`)
- `KAFKA_TOPIC`: Kafka topic name (default: `weather`)
- `KAFKA_DISABLED`: Set to `true` to bypass Kafka and insert directly to PostgreSQL (default: `false`). **Disabled in code** — the direct-DB fallback is commented out; uncomment in `config.py` and `producer.py` to use.
- `KAFKA_SECURITY_PROTOCOL`: `PLAINTEXT` or `SASL_PLAINTEXT` (default: `SASL_PLAINTEXT`)
- `KAFKA_SASL_MECHANISM`: SASL mechanism (default: `SCRAM-SHA-256`)
- `KAFKA_USERNAME` / `KAFKA_PASSWORD`: SASL credentials (default: empty)
- `KAFKA_GROUP_ID`: Consumer group id (default: `weather-group`)

> The Kafka deployment in this repo uses PLAINTEXT listeners (no SASL). The app and consumer deployments set `KAFKA_SECURITY_PROTOCOL=PLAINTEXT` and `KAFKA_SASL_MECHANISM=PLAIN` to match. If you use an external Kafka with SASL/SCRAM, override these.

**Application:**
- `COMPONENT`: Which component to run: `web`, `producer`, or `consumer` (default: `web`)
- `STATUS_PAGE_ENABLED`: Set to `true` to enable the `/status` page and show its link on the home page (default: `false`)

Enable or disable the status page at runtime with `oc set env` (applies to the `rahti-weather` web deployment):

```bash
# Enable the /status page
oc set env deployment/rahti-weather STATUS_PAGE_ENABLED=true

# Disable the /status page
oc set env deployment/rahti-weather STATUS_PAGE_ENABLED=false
```

The change triggers a rolling restart of the web pod. Once it's ready, visit `https://<your-route-host>/status` (or use the link on the home page).

### Database Setup

The application will automatically create the required `weather` table if it doesn't exist.

### Kafka Topics

The application uses a Kafka topic named `weather` for communication between producer and consumer. The topic name can be overridden with the `KAFKA_TOPIC` environment variable. The topic is auto-created by the broker on first produce (auto.create.topics.enable defaults to true).

## Deployment Components

The project deploys four components, each with its own YAML file:

| File | Component | Description |
| --- | --- | --- |
| `kafka-deployment.yaml` | Kafka | Kafka 4.3.1 broker (KRaft mode, single node). Image from CSC's Satama registry: `satama.csc.fi/library/kafka:4.3.1`. See step 2 above for how to make it available in your project. |
| `postgresql-deployment.yaml` | PostgreSQL | Database for storing weather data. Uses `bitnamilegacy/postgresql:15.3.0`. |
| `app-deployment.yaml` | Web + Producer | Flask web UI plus the producer that fetches weather data and publishes to Kafka. |
| `consumer-deployment.yaml` | Consumer | Subscribes to Kafka and inserts messages into PostgreSQL. |

## Scaling

You can scale the components as needed:

```bash
# Scale web interface
oc scale deployment/rahti-weather --replicas=2
```

## Troubleshooting

- Check pod logs: `oc logs <pod-name>`
- Check events: `oc get events`
- Check environment variables: `oc set env deployment/<deployment-name> --list`
- Check image streams: `oc get imagestream`. If missing, recreate with `oc import-image <name>:<tag> --from=<source> --confirm` or `oc create imagestream <name>`
- Port forward to test locally: `oc port-forward svc/rahti-weather 8080:8080`
- Works with `curl` over HTTP but not in the browser? Check whether the browser is forcing HTTPS (Rahti routes often redirect HTTP to HTTPS) or caching an earlier error page. Try an incognito window, or hard-refresh / clear cache. Confirm the route with `oc get route rahti-weather`.

## Cleanup

> **Warning:** these commands permanently delete all deployed resources and all database data (PostgreSQL uses `emptyDir`, so data does not survive pod deletion). They only affect resources labeled with the app names below — they do not delete your OpenShift project. Run them only when you want to tear down the deployment completely.

```bash
oc delete all -l app=rahti-weather
oc delete all -l app=rahti-weather-consumer
oc delete all -l app=kafka
oc delete all -l app=postgresql
oc delete is rahti-weather
oc delete is kafka
```

## Reset Project Files to Defaults

If you used the Quick Setup for Testing (or manually replaced the placeholders with your own namespace and credentials), you can restore the project files to their original default state. This replaces your namespace with the `<namespace>` placeholder in all deployment YAMLs and restores the `<your-user>` / `<your-password>` / `<your-db>` placeholders in `postgresql-deployment.yaml`:

```bash
# Restore <namespace> placeholder in all deployment YAMLs
sed -i "s|image-registry.openshift-image-registry.svc:5000/[^/]*/|image-registry.openshift-image-registry.svc:5000/<namespace>/|g" app-deployment.yaml consumer-deployment.yaml
sed -i "s|image-registry.apps.2.rahti.csc.fi/[^/]*/|image-registry.apps.2.rahti.csc.fi/<namespace>/|g" kafka-deployment.yaml

# Restore credential placeholders in postgresql-deployment.yaml
sed -i "s/weatheruser/<your-user>/g; s/weatherpass/<your-password>/g; s/weatherdb/<your-db>/g" postgresql-deployment.yaml
```

After running these, the files are back to the state they ship in from the repository, ready for a fresh deploy.
