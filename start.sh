#!/bin/bash

# --- 1. SET PATH FOR VIRTUAL ENVIRONMENT ---
# Railway often places the Python binary in a .venv/bin folder.
# We explicitly export this path so 'python' and 'uvicorn' commands work.
export PATH="$VIRTUAL_ENV/bin:$PATH"

# --- 2. Data Setup ---
# Use the explicit 'python' command, which is now sourced from $VIRTUAL_ENV/bin
echo "Running data setup script..."
python backend/function/outlet_scraper.py

# --- 3. Start the Server ---
# We use the explicit 'python -m' to run uvicorn as a module, 
# which is more robust than running 'uvicorn' directly.
echo "Starting Uvicorn server..."
# Set the Python path so imports like 'function.rag_service' work.
export PYTHONPATH=backend
python -m uvicorn backend.api_server:app --host 0.0.0.0 --port $PORT --workers 4
