# 🧠 Mindhive AI Assistant Assessment

This repository contains the complete solution for the **Mindhive AI Software Engineer Assessment**, implementing a multi-turn, agentic chatbot that integrates **RAG**, **Text-to-SQL**, and a **Calculator Tool** using **FastAPI (Python)** for the backend and **React (Vite)** for the frontend.

---

## 1. Architecture Overview (Parts 1–4)

The system follows a modern, decoupled **Microservices / Agentic architecture** built on four key layers:

### 🧩 A. The Agentic Planner (The “Brain” – `agent_core.py`)
- **Technology:** LangChain Agent Executor (`create_agent`) powered by Groq (`llama-3.3-70b-versatile`)  
- **Function:** Handles all Part 1 (Memory) and Part 2 (Planning) requirements  
- **Memory:** Maintained by passing the full `chat_history` (list of `AIMessage` / `HumanMessage` objects) to every invocation, allowing sequential conversations (e.g., *“What was the answer to my first question?”*)  
- **Action Selection:** The LLM inspects user intent and decides which of the three internal tools to execute.

---

### ⚙️ B. Core Services (The “Tools”)
The agent uses direct function invocation to access three primary tools, eliminating network latency and deadlocks:

| Tool Name              | Endpoint Type  | Backend Technology         | Data Source                 |
|-------------------------|----------------|-----------------------------|------------------------------|
| `calculator`            | Simple Function | Python `safe_eval`          | N/A                          |
| `zus_product_information` | RAG Pipeline   | LangChain LCEL, FAISS       | ZUS Drinkware Data           |
| `zus_outlet_database`   | Text-to-SQL     | LangChain SQL Agent         | SQLite (`zus_outlets.db`)    |

---

### 🌐 C. The API Gateway (`api_server.py`)
- **Technology:** FastAPI with `uvicorn`  
- **Function:** Exposes the unified `/chat` endpoint, serving as the single point of contact for the frontend.  
  - Loads all core services (`rag_chain`, `sql_chain`, `agent_executor`) during the lifespan event.

---

### 💻 D. The Frontend (`frontend/src/App.jsx`)
- **Technology:** React (Vite), styled with TailwindCSS  
- **Function:** Handles Part 6 (Chat UI), managing message history, persistent storage (`localStorage`), and user interaction (Composer, Quick Actions)

---

## 2. Setup and Installation Guide

### 🔧 Prerequisites
- Python 3.10+
- Node.js & npm (for frontend)
- Groq API Key (set as environment variable)

---

### 🐍 Backend Installation

```bash
# Clone repository
git clone [your_repo_url]
cd Mindhive_Chatbot

# Create and activate environment
conda create -n mindhive python=3.10
conda activate mindhive

# Install dependencies
pip install -r requirements.txt
# (Requirements include: fastapi, uvicorn, python-multipart, python-dotenv, requests,
# langchain-groq, langchain-community, sqlalchemy, beautifulsoup4, faiss-cpu)
```

#### 🔑 Set Environment Variables
Create a `.env` file in the root directory:
```bash
GROQ_API_KEY="your_secret_groq_key_here"
```

#### 🗂️ Data Ingestion (Part 4 – Products & Outlets)
```bash
cd backend
python function/outlet_scraper.py
# Run ingestion script for RAG if index is missing
```

---

### 🌐 Frontend Installation
```bash
cd frontend
npm install
```

---

### ▶️ Running the Application

This application requires **two terminals** running concurrently:

**Terminal 1 – Backend:**
```bash
cd backend
python api_server.py
# Server: http://127.0.0.1:8000
```

**Terminal 2 – Frontend:**
```bash
cd frontend
npm run dev
# Frontend: http://localhost:5173
```

Access the Chat UI in your browser at [http://localhost:5173](http://localhost:5173)

---

## 3. API Specification

The backend exposes **four FastAPI endpoints**:
- Three internal tool endpoints
- One primary `/chat` endpoint for frontend

---

### 🗨️ 4.1 `/chat` Endpoint (Primary)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat` | Receives user message + chat history, returns agent’s response |

#### Request Body (JSON)
```json
{
  "message": "What is the price of the all day cup?",
  "history": [
    {"type": "human", "content": "Hello"},
    {"type": "ai", "content": "Hello! How can I help?"}
  ]
}
```

#### Response (200 OK)
```json
{
  "answer": "The All Day Cup (500ml) is priced at RM 79.00."
}
```

---

### 🧰 4.2 Internal Tool Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/products?query=<nl_query>` | RAG: Answer questions about ZUS drinkware via FAISS vector store |
| `GET` | `/outlets?query=<nl_query>` | Text-to-SQL: Query outlet locations using SQLite |
| `GET` | `/calculate?expression=<math_expr>` | Calculator: Perform simple math safely via `safe_eval` |

---

## 4. Key Design Decisions & Trade-offs

### 🚦 A. Deadlock Resolution (Performance & Stability)

| Challenge | Solution | Rationale |
|------------|-----------|------------|
| Server Deadlock (Part 2/4 Integration) | **Direct Invocation**: Changed agent tool functions to call RAG/SQL chains directly (`rag_chain.invoke(query)`) instead of using HTTP requests. | Prevents single-threaded Uvicorn from freezing. Boosts speed and stability. |
| Model Brittleness | Used `llama-3.3-70b-versatile` and defined strict system prompts. | Smaller models (8b) hallucinated tools or entered recursion loops. The 70b model ensures reliability. |

---

### 🧱 B. Robustness & Error Handling (Part 5)
- **SQL Injection Prevention:**  
  Uses LangChain `create_sql_agent`, preventing malicious SQL (e.g., `''); DROP TABLE outlets; --`).
- **API Downtime Handling:**  
  All tool calls wrapped in `try...except` blocks; gracefully handles Groq API errors or division-by-zero.
- **Calculator Safety:**  
  `/calculate` endpoint uses Python’s `ast` module to ensure only math expressions are executed.

---

### 🧭 C. Frontend Implementation (Part 6)
- **Framework Choice:** React/Vite chosen for modern web stack preference.
- **Architecture:** Fully decoupled from Python-specific dependencies (no Streamlit/Gradio).
- **State Management:**  
  Chat history stored in `localStorage` for persistence across refreshes.

---

## 🏁 Summary
This project demonstrates an end-to-end, production-ready **AI Assistant architecture** with:
- Multi-turn conversational reasoning (memory)
- Agent-based planning
- RAG, Text-to-SQL, and Calculator tool integration
- FastAPI backend + React (Vite) frontend
- Optimized, deadlock-free internal architecture
