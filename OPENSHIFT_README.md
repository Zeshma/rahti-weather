# Rahti Weather - OpenShift Deployment Guide

## Overview
This guide explains how to deploy the Rahti Weather application on OpenShift.

## Prerequisites
- OpenShift CLI (`oc`) installed and logged in
- Access to an OpenShift project
- PostgreSQL database instance (can be deployed on OpenShift or external)
- Kafka instance (can be deployed on OpenShift or external)

## Deployment Steps

### 1. Build and Push Container Image

```bash
# Build the container image
oc new-build python:3.10-slim --name=rahti-weather --binary

# Start the build and upload files
oc start-build rahti-weather --from-dir=. --follow
```

### 2. Deploy Using Template

```bash
# Process the template
oc process -f openshift-template.yaml \
  -p DB_HOST=<your-postgresql-host> \
  -p DB_NAME=<your-db-name> \
  -p DB_USER=<your-db-username> \
  -p DB_PASSWORD=<your-db-password> \
  -p DB_PORT=<your-db-port> \
  -p KAFKA_BOOTSTRAP=<your-kafka-brokers> \
  | oc apply -f -
```

### 3. Verify Deployment

```bash
# Check pods are running
oc get pods

# Check services
oc get svc

# Check routes
oc get routes
```

### 4. Access the Application

The web interface will be available at the route URL shown in `oc get routes`.

### 5. Health Checks

The application includes comprehensive health checks for all components:

#### Health Check Endpoints

- **Web Application**: `http://<route-url>/health`
- **Producer**: `http://<producer-pod-ip>:8081/health`
- **Consumer**: `http://<consumer-pod-ip>:8082/health`

#### Kubernetes Probes

All components have liveness and readiness probes configured:

- **Liveness Probe**: Restarts unhealthy containers (30s initial delay, 10s interval)
- **Readiness Probe**: Controls traffic routing (15s initial delay, 5s interval)

#### Testing Health Checks

```bash
# Test web health check
oc port-forward svc/weather-web 8080:8080
curl http://localhost:8080/health

# Test producer health check (port forward to a producer pod)
PRODUCER_POD=$(oc get pods -l app=weather,component=producer -o jsonpath='{.items[0].metadata.name}')
oc port-forward pod/$PRODUCER_POD 8081:8081
curl http://localhost:8081/health

# Test consumer health check
CONSUMER_POD=$(oc get pods -l app=weather,component=consumer -o jsonpath='{.items[0].metadata.name}')
oc port-forward pod/$CONSUMER_POD 8082:8082
curl http://localhost:8082/health
```

#### Health Check Responses

Healthy response:
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2026-05-18T14:01:47.340727"
}
```

Unhealthy response (HTTP 500):
```json
{
  "status": "unhealthy",
  "database": "connection failed",
  "timestamp": "2026-05-18T14:01:47.340727"
}
```

### 6. Monitoring Health Checks

```bash
# Check probe status for a pod
oc describe pod <pod-name> | grep -A 5 "Liveness\|Readiness"

# View health check events
oc get events --field-selector reason=Unhealthy

# Check pod readiness
oc get pods -l app=weather --field-selector=status.phase=Running
```

## Configuration

### Environment Variables

The application uses the following environment variables (with sensible defaults):

- `DB_HOST`: PostgreSQL host (default: `<db-host>`)
- `DB_NAME`: PostgreSQL database name (default: `<db-name>`)
- `DB_USER`: PostgreSQL username (default: `<db-user>`)
- `DB_PASSWORD`: PostgreSQL password (default: `<db-password>`)
- `DB_PORT`: PostgreSQL port (default: `<db-port>`)
- `KAFKA_BOOTSTRAP`: Kafka bootstrap servers (default: `<kafka-bootstrap>`)

### Database Setup

The application will automatically create the required `weather` table if it doesn't exist.

### Kafka Topics

The application uses a Kafka topic named `weather` for communication between producer and consumer.

## Scaling

You can scale the components as needed:

```bash
# Scale web interface
oc scale deployment/weather-web --replicas=2

# Scale producer (usually 1 is enough)
oc scale deployment/weather-producer --replicas=1

# Scale consumer (can be increased for higher throughput)
oc scale deployment/weather-consumer --replicas=2
```

## Monitoring

The application includes built-in health monitoring:

### Health Check Monitoring

```bash
# Monitor health check failures
oc get events --watch --field-selector reason=Unhealthy

# Check probe status across all pods
oc get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.containerStatuses[0].ready}{"\n"}'

# View detailed probe information
oc describe pod <pod-name> | grep -A 10 -B 2 "Probe"
```

### Custom Monitoring

Consider adding Prometheus monitoring by creating appropriate ServiceMonitors:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: weather-monitor
  labels:
    app: weather
spec:
  selector:
    matchLabels:
      app: weather
  endpoints:
  - port: web
    path: /health
    interval: 30s
```

For advanced monitoring, you can also use OpenShift's built-in monitoring capabilities.

## Troubleshooting

- Check pod logs: `oc logs <pod-name>`
- Check events: `oc get events`
- Check environment variables: `oc set env deployment/<deployment-name> --list`

## Cleanup

```bash
oc delete all -l app=weather
oc delete secret weather-db-secret
oc delete is rahti-weather