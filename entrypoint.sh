#!/bin/bash

# Entry point script that runs the appropriate component based on environment
set -e

echo "Starting weather application..."
echo "Component: ${COMPONENT:-web}"
echo "Working directory: $(pwd)"
echo "Files in directory: $(ls -la)"
echo "Producer file exists: $(test -f producer.py && echo 'YES' || echo 'NO')"

case "$COMPONENT" in
    "web")
        echo "Running web application..."
        echo "Starting producer in background..."
        python producer.py &
        PRODUCER_PID=$!
        echo "Producer started with PID: $PRODUCER_PID"
        exec python app.py
        ;;
    "producer")
        echo "Running producer..."
        echo "About to execute: python producer.py"
        exec python producer.py
        ;;
    "consumer")
        echo "Running consumer..."
        exec python consumer.py
        ;;
    *)
        echo "Unknown component: $COMPONENT"
        echo "Running web application by default..."
        echo "Starting producer in background..."
        python producer.py &
        PRODUCER_PID=$!
        echo "Producer started with PID: $PRODUCER_PID"
        exec python app.py
        ;;
esac
