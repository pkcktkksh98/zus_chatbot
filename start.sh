#!/bin/bash

# --- 1. Data Setup (CRUCIAL FIX) ---
# We use 'python3 -m' to invoke the scraper, ensuring we use the Python interpreter 
# installed in the container environment.
echo "Running data setup script..."
python3 backend/function/outlet_scraper.py

# --- 2. Start the Server (CRUCIAL FIX) ---
# We invoke Uvicorn directly as a module using the Python interpreter,
# which is the most reliable way to start the ASGI server in containers.
echo "Starting Uvicorn server..."
# Set the Python path so imports like 'function.rag_service' work.
export PYTHONPATH=backend
python3 -m uvicorn backend.api_server:app --host 0.0.0.0 --port $PORT --workers 4

# If the above fails, an alternative safe command is:
# exec gunicorn api_server:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT