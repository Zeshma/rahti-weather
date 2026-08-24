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

### 1. Deploy Infrastructure (Kafka and PostgreSQL)

First, deploy Kafka and PostgreSQL using the provided deployment files:

```bash
# Deploy Kafka
oc apply -f kafka-deployment.yaml

# Deploy PostgreSQL
oc apply -f postgresql-deployment.yaml

# Wait for pods to be ready
oc wait --for=condition=ready pod -l app=kafka --timeout=300s
oc wait --for=condition=ready pod -l app=postgresql --timeout=300s
```

### 2. Build and Push Container Image

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

### 3. Deploy the Application

```bash
# Deploy the application
oc apply -f app-deployment.yaml

# Wait for the pod to be ready
oc wait --for=condition=ready pod -l app=rahti-weather --timeout=300s
```

### 4. Verify Deployment

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

For this project, the URL is: http://rahti-weather-justtest.2.rahtiapp.fi

### 6. Verify Data Flow

Once all components are running, verify the complete data flow:

```bash
# Check application logs
oc logs -l app=rahti-weather --tail=20

# Check if data is being inserted
oc exec <rahti-weather-pod> -- python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8080/').read().decode()[:500])"
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

The application uses the following environment variables:

- `DB_HOST`: PostgreSQL host (default: "postgresql")
- `DB_NAME`: PostgreSQL database name (default: "weatherdb")
- `DB_USER`: PostgreSQL username (default: "weatheruser")
- `DB_PASSWORD`: PostgreSQL password (default: "weatherpass")
- `DB_PORT`: PostgreSQL port (default: "5432")
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka bootstrap servers (default: "kafka:9092")
- `COMPONENT`: Application component (web, producer, consumer)
- `KAFKA_DISABLED`: Set to "true" to use direct DB insert mode (default: "false")

### Database Setup

The application will automatically create the required `weather` table if it doesn't exist.

### Kafka Topics

The application uses a Kafka topic named `weather-data` for communication between producer and consumer.

## Current Deployment Notes

### What's Currently Deployed
- Kafka (Bitnami) - Running at `kafka:9092`
- PostgreSQL - Running at `postgresql:5432`
- Weather Application - Running with Kafka disabled, using direct DB insert mode

### Current Configuration
- KAFKA_DISABLED=true (producer inserts directly to PostgreSQL)
- COMPONENT=web (runs web server with producer in background)
- Database: weatherdb with weatheruser credentials

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
oc delete all -l app=kafka
oc delete all -l app=postgresql
oc delete is rahti-weather
oc delete is python