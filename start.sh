#!/bin/bash

# --- 1. Installation ---
# Railway automatically installs requirements.txt, but we ensure the environment is ready.

# --- 2. Data Setup (Crucial for SQL Agent) ---
# Create the SQLite database and run the scraper before starting the server.
echo "Running data setup script..."
python3 backend/function/outlet_scraper.py

# --- 3. Start the Server ---
# Navigate to the backend directory and run Uvicorn.
# We explicitly set the Python path so imports like 'function.rag_service' work.
echo "Starting Uvicorn server..."
export PYTHONPATH=backend
uvicorn backend.api_server:app --host 0.0.0.0 --port $PORT --workers 4

# NOTE: The above command assumes your main file is named api_server.py 
# and the app instance inside is named 'app'.
