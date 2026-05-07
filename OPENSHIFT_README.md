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

Consider adding monitoring by creating appropriate ServiceMonitors or using OpenShift's built-in monitoring.

## Troubleshooting

- Check pod logs: `oc logs <pod-name>`
- Check events: `oc get events`
- Check environment variables: `oc set env deployment/<deployment-name> --list`

## Cleanup

```bash
oc delete all -l app=weather
oc delete secret weather-db-secret
oc delete is rahti-weather