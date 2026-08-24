# Rahti Weather - OpenShift Deployment Guide

## Overview
This guide explains how to deploy the Rahti Weather application on OpenShift. The application provides a complete weather monitoring pipeline that fetches data from Open-Meteo API, processes it through Kafka, stores it in PostgreSQL, and displays it via a web interface.

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

### Example Configuration
```bash
# Example values (replace with your actual credentials)
export DB_HOST="postgresql"
export DB_NAME="weatherdb"
export DB_USER="weatheruser"
export DB_PASSWORD="weatherpass"
export DB_PORT="5432"
export KAFKA_BOOTSTRAP_SERVERS="kafka:9092"
```

## Deployment Steps

### 1. Set Your Credentials

The deployment YAMLs do not contain hardcoded credentials. Before applying them, decide on your database credentials and set them on the PostgreSQL deployment:

```bash
# Choose your own credentials
oc set env deployment/postgresql \
  POSTGRESQL_USERNAME=<your-user> \
  POSTGRESQL_PASSWORD=<your-password> \
  POSTGRESQL_DATABASE=<your-db>
```

The app and consumer deployments read database credentials from the same `DB_*` environment variables. Set them to match:

```bash
oc set env deployment/rahti-weather \
  DB_USER=<your-user> DB_PASSWORD=<your-password> DB_NAME=<your-db>

oc set env deployment/rahti-weather-consumer \
  DB_USER=<your-user> DB_PASSWORD=<your-password> DB_NAME=<your-db>
```

> Note: the YAML files use `<your-user>` / `<your-password>` / `<your-db>` placeholders. You can either edit the YAMLs before applying, or apply first and then use `oc set env` as shown above.

### 2. Deploy Infrastructure (Kafka and PostgreSQL)

First, make the Kafka image available in your project (see the "Kafka image" section above), then deploy Kafka and PostgreSQL:

```bash
# Deploy Kafka
oc apply -f kafka-deployment.yaml

# Deploy PostgreSQL
oc apply -f postgresql-deployment.yaml

# Wait for pods to be ready
oc wait --for=condition=ready pod -l app=kafka --timeout=300s
oc wait --for=condition=ready pod -l app=postgresql --timeout=300s
```

### 3. Build and Push Container Image

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

#### Option C: Using OpenShift Build (Alternative)
```bash
# Create a build configuration
oc new-build python:3.10-slim --name=rahti-weather --binary

# Start the build
oc start-build rahti-weather --from-dir=. --follow
```

### 4. Deploy the Application and Consumer

The image references in `app-deployment.yaml` and `consumer-deployment.yaml` contain a `<namespace>` placeholder. Replace it with your project name before applying, or patch the image after deploying:

```bash
# Replace <namespace> with your project name in both files
NAMESPACE=$(oc project -q)
sed -i "s/<namespace>/${NAMESPACE}/g" app-deployment.yaml consumer-deployment.yaml

# Deploy the web application (includes producer)
oc apply -f app-deployment.yaml

# Deploy the consumer
oc apply -f consumer-deployment.yaml

# Wait for pods to be ready
oc wait --for=condition=ready pod -l app=rahti-weather --timeout=300s
oc wait --for=condition=ready pod -l app=rahti-weather-consumer --timeout=300s
```

### 5. Verify Deployment

```bash
# Check pods are running
oc get pods

# Check services
oc get svc

# Check routes
oc get routes
```

### 5. Access the Application

The web interface will be available at the route URL shown in `oc get routes`.

Find yours with:
```bash
oc get route rahti-weather -o jsonpath='{.spec.host}{"\n"}'
```

### 6. Verify Data Flow

Once all components are running, verify the complete data flow:

```bash
# Check producer logs (should show "Sent to Kafka")
oc logs -l app=rahti-weather --tail=20

# Check consumer logs (should show "Received message" and "Inserted")
oc logs -l app=rahti-weather-consumer --tail=20

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

## Application Architecture

The Rahti Weather application consists of three main components:

### 1. Web Application
- **Purpose**: Displays weather data in a user-friendly web interface
- **Port**: 8080
- **Technology**: Flask web framework

### 2. Producer
- **Purpose**: Fetches weather data from Open-Meteo API and publishes to Kafka (or directly to DB if Kafka disabled)
- **Locations**: Oulu (65.01, 25.47) and Lapinaho (65.89532, 28.30994)
- **Frequency**: Every 15 minutes
- **Port**: 8081 (health checks)
- **Technology**: Python with requests library

### 3. Consumer
- **Purpose**: Subscribes to Kafka, processes messages, and stores in PostgreSQL
- **Port**: 8082 (health checks)
- **Technology**: Kafka Consumer with PostgreSQL integration

## Data Flow

```
Open-Meteo API → Producer → [Kafka Topic] → Consumer → PostgreSQL → Web Interface
                 (or direct DB insert if Kafka disabled)
```

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
- `KAFKA_DISABLED`: Set to `true` to bypass Kafka and insert directly to PostgreSQL (default: `false`)
- `KAFKA_SECURITY_PROTOCOL`: `PLAINTEXT` or `SASL_PLAINTEXT` (default: `SASL_PLAINTEXT`)
- `KAFKA_SASL_MECHANISM`: SASL mechanism (default: `SCRAM-SHA-256`)
- `KAFKA_USERNAME` / `KAFKA_PASSWORD`: SASL credentials (default: empty)
- `KAFKA_GROUP_ID`: Consumer group id (default: `weather-group`)

> The Kafka deployment in this repo uses PLAINTEXT listeners (no SASL). The app and consumer deployments set `KAFKA_SECURITY_PROTOCOL=PLAINTEXT` and `KAFKA_SASL_MECHANISM=PLAIN` to match. If you use an external Kafka with SASL/SCRAM, override these.

**Application:**
- `COMPONENT`: Which component to run: `web`, `producer`, or `consumer` (default: `web`)

### Database Setup

The application will automatically create the required `weather` table if it doesn't exist.

### Kafka Topics

The application uses a Kafka topic named `weather` for communication between producer and consumer. The topic name can be overridden with the `KAFKA_TOPIC` environment variable. The topic is auto-created by the broker on first produce (auto.create.topics.enable defaults to true).

## Deployment Components

The project deploys four components, each with its own YAML file:

| File | Component | Description |
| --- | --- | --- |
| `kafka-deployment.yaml` | Kafka | Kafka 4.3.1 broker (KRaft mode, single node). Image from CSC's Satama registry: `satama.csc.fi/library/kafka:4.3.1`. See below for how to make it available in your project. |
| `postgresql-deployment.yaml` | PostgreSQL | Database for storing weather data. Uses `bitnamilegacy/postgresql:15.3.0`. |
| `app-deployment.yaml` | Web + Producer | Flask web UI plus the producer that fetches weather data and publishes to Kafka. |
| `consumer-deployment.yaml` | Consumer | Subscribes to Kafka and inserts messages into PostgreSQL. |

### Kafka image

The `kafka-deployment.yaml` references `image-registry.apps.2.rahti.csc.fi/<namespace>/kafka:4.3.1`. CSC publishes a maintained Kafka image at `satama.csc.fi/library/kafka:4.3.1` (publicly pullable, no auth needed). Before deploying, pull it from Satama and push it to your project's registry:

```bash
NAMESPACE=$(oc project -q)
podman pull satama.csc.fi/library/kafka:4.3.1
podman tag satama.csc.fi/library/kafka:4.3.1 image-registry.apps.2.rahti.csc.fi/${NAMESPACE}/kafka:4.3.1
podman push image-registry.apps.2.rahti.csc.fi/${NAMESPACE}/kafka:4.3.1
```

Then replace `<namespace>` in `kafka-deployment.yaml` with your project name (or use `oc apply` with the in-cluster registry URL and patch the image afterward).

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
- Port forward to test locally: `oc port-forward svc/rahti-weather 8080:8080`

## Cleanup

```bash
oc delete all -l app=rahti-weather
oc delete all -l app=rahti-weather-consumer
oc delete all -l app=kafka
oc delete all -l app=postgresql
oc delete is rahti-weather
oc delete is kafka