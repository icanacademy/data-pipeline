#!/bin/bash

# ICAN Data Center - Startup Script
# Double-click this file to start the ICAN Data Center

cd "$(dirname "$0")"

echo "=========================================="
echo "       ICAN Data Center"
echo "=========================================="
echo ""

# Start Cloudflare tunnel if not already running
if ! pgrep -f "cloudflared tunnel run cosmodrive" > /dev/null 2>&1; then
    echo "🌐 Starting Cloudflare Tunnel..."
    cloudflared tunnel run cosmodrive &
    sleep 2
    echo "✅ Cloudflare Tunnel started"
else
    echo "🌐 Cloudflare Tunnel already running"
fi
echo "🌍 Public URL: https://datacenter.icanacademy.work"
echo ""

# Check if Python virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Installing dependencies..."
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Check if TypeDB is running
echo "Checking TypeDB..."
if ! docker ps | grep -q typedb; then
    echo "Starting TypeDB..."
    if docker ps -a | grep -q typedb; then
        docker start typedb
    else
        docker run -d --name typedb -p 1729:1729 vaticle/typedb:latest
    fi
    echo "Waiting for TypeDB to start..."
    sleep 5
else
    echo "TypeDB is already running."
fi

# Initialize database if needed
echo ""
echo "Initializing database..."
python scripts/setup_typedb.py 2>/dev/null || echo "Database may already exist, continuing..."

# Run sync
echo ""
echo "Syncing data from all sources..."
python scripts/run_sync.py

# Start the API
echo ""
echo "=========================================="
echo "  Starting Web Interface"
echo "=========================================="
echo ""
echo "Opening http://localhost:8080 in your browser..."
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Open browser after a short delay
(sleep 2 && open http://localhost:8080) &

# Start the API server
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8080
