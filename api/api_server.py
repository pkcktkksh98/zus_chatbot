import os
import ast
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware # Import CORS
from pydantic import BaseModel
from typing import List, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage

# Import our new RAG service
# Assuming the structure is: backend/api_server.py imports from backend/function/rag_service.py
# If your folder structure is flat (backend/rag_service.py), change this import:
try:
    from .function.rag_service import initialize_chains
    from .function.agent_service import initialize_agent_executor, safe_eval
except ImportError:
    from function.rag_service import initialize_chains
    from function.agent_service import initialize_agent_executor, safe_eval #type: ignore


# --- Load Environment ---
load_dotenv()

# --- Global Variables ---
rag_chain = None
sql_chain = None
main_agent_executor = None

# --- Lifespan Context Manager (Fixes the TypeError) ---
# NOTE: This must be `def` (synchronous generator) when using @asynccontextmanager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    On server startup, load all models and services into memory.
    """
    global rag_chain, sql_chain, main_agent_executor
    print("Server starting up (lifespan startup)...")
    
    try:
        # Load RAG and SQL chains
        rag_chain, sql_chain = await initialize_chains()
    except Exception as e:
        print(f"FATAL: RAG/SQL chain initialization failed: {e}")
    
    try:
        # Load the main agent executor
        main_agent_executor = initialize_agent_executor(rag_chain, sql_chain)#type:ignore
        print("Main agent executor initialized.")
    except Exception as e:
        # This catch is vital. It logs the error but allows the server to start
        # so the user can debug the 503 error from the /chat endpoint.
        print(f"FATAL: Agent Executor failed to initialize: {e}")
        main_agent_executor = None
        
    print("All necessary services loaded.")
    
    yield # Server is now running
    
    # Code to run on SHUTDOWN:
    print("Server shutting down (lifespan shutdown)...")


# --- FastAPI App Initialization ---
# Pass the lifespan function when creating the app instance
app = FastAPI(
    title="Mindhive Assessment API",
    description="API for ZUS Coffee product RAG and outlet Text2SQL.",
    version="1.0.0",
    lifespan=lifespan # Pass the lifespan function here
)

# --- ADD CORS MIDDLEWARE ---
# This allows your React app (e.g., from localhost:3000)
# to make requests to this API (at localhost:8000)
# --- ADD CORS MIDDLEWARE (Finalized) ---
origins = [
    # Local Development
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",

    # Vercel Production Domain (MUST be HTTPS and exact)
    "https://zus-chatbot-tphk.vercel.app", 

    # For local file testing
    "null", 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"], # Explicitly allow the OPTIONS method
    allow_headers=["*"], 
)

# --- Pydantic Models for /chat endpoint ---
# Defines the expected JSON structure for our chat requests
class ChatMessage(BaseModel):
    # This matches the LangChain HumanMessage/AIMessage structure
    type: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage]

# --- Helper function for safe math ---
def safe_eval(expression: str) -> float:
    """
    Safely evaluates a simple mathematical expression.
    Prevents unsafe operations.
    """
    # 1. Parse the expression into an Abstract Syntax Tree (AST)
    tree = ast.parse(expression, mode='eval')

    # 2. Whitelist allowed operations
    allowed_nodes = {
        ast.Expression, ast.Call, ast.Name, ast.Load,
        ast.BinOp, ast.UnaryOp, ast.Num, ast.Constant, # Python 3.8+ uses Constant
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd
    }
    
    # 3. Walk the tree and check all nodes
    for node in ast.walk(tree):
        if type(node) not in allowed_nodes:
            raise ValueError(f"Disallowed operation in expression: {type(node).__name__}")

    # 4. If all nodes are safe, compile and execute
    # We pass an empty locals/globals dict to prevent access to built-ins
    return eval(compile(tree, "<string>", "eval"), {}, {})

# --- API Endpoints ---
@app.get("/", tags=["Health"])
async def get_health_check():
    """A simple health check endpoint to confirm the API is running."""
    return {"status": "ok", "message": "API is running and all services are loaded."}

# --- 4. Main Chat Endpoint (NEW) ---
@app.post("/chat", tags=["Agent"])
async def chat_with_agent(request: ChatRequest):
    """
    Main endpoint for the React frontend.
    Receives the current message and all chat history,
    invokes the agent, and returns the AI's response.
    """
    global main_agent_executor
    if not main_agent_executor:
        raise HTTPException(status_code=503, detail="Agent is not initialized.")
    
    try:
        # 1. Convert Pydantic models back into LangChain message objects
        # We must use the exact 'type' and 'content' keys
        # Convert Pydantic models into LangChain Message OBJECTS
        langchain_history = []
        for msg in request.history:
            if msg.type == "human":
                langchain_history.append(HumanMessage(content=msg.content))
            elif msg.type == "ai":
                langchain_history.append(AIMessage(content=msg.content))

        # Add the new human message
        langchain_history.append(HumanMessage(content=request.message))
        
        # 3. Invoke the agent
        # We use the 'messages' key, as required by create_agent
        response = main_agent_executor.invoke({
            "messages": langchain_history
        })
        
        # 4. Extract and return the final AI response
        # The agent returns the full history, we just want the last message
        ai_response = response["messages"][-1].content
        return {"answer": ai_response}
    
    except Exception as e:
        import traceback
        print(f"Chat Endpoint Error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# --- 1. Product RAG Endpoint ---
@app.get("/products", tags=["Tool"])
async def get_product_info(query: str):
    """
    Retrieve product information (Drinkware) using RAG.
    """
    global rag_chain
    if not rag_chain:
        raise HTTPException(status_code=503, detail="RAG service is not ready. Initialization may have failed.")
    
    try:
        # The LCEL RAG chain returns a dictionary: {"answer": str, "context": str}
        response = await rag_chain.ainvoke(query) 
        
        return {
            "query": query,
            "answer": response["answer"],
            "context": response["context"] 
        }
    except Exception as e:
        import traceback
        print(f"RAG Query Failed for input '{query}': {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error processing RAG query: {e.__class__.__name__} - {str(e)}")


# --- 2. Outlets Text2SQL Endpoint (Stub) ---
@app.get("/outlets", tags=["Tool"])
async def get_outlet_info(query: str):
    """
    Retrieve outlet information (Location, hours, status) using Text-to-SQL.
    """
    global sql_chain
    if not sql_chain:
        raise HTTPException(status_code=503, detail="SQL service is not ready.")

    try:
        # The SQL chain is synchronous (RunnableLambda wrapper), so we use .invoke()
        response = sql_chain.invoke(query)
        
        # The output is structured by our custom run_sql_query wrapper
        return {
            "query": response["query"],
            "answer": response["answer"],
            "raw_sql_agent_response": response["raw_sql_agent_response"]
        }
    except Exception as e:
        import traceback
        print(f"SQL Query Failed for input '{query}': {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error processing SQL query: {e.__class__.__name__} - {str(e)}")

# --- 3. Calculator Endpoint (NEW) ---
@app.get("/calculate", tags=["Tool"])
async def get_calculation_result(expression: str):
    """
    Performs simple arithmetic calculation safely.
    """
    try:
        # Use our safe_eval function
        result = safe_eval(expression)
        return {"expression": expression, "result": result, "status": "success"}
    except (SyntaxError, ZeroDivisionError, ValueError, TypeError) as e:
        # This will catch "10 / 0" and return a 400
        raise HTTPException(
            status_code=400,
            detail=f"Invalid expression or error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal calculation error: {str(e)}"
        )
    
if __name__ == "__main__":
    import uvicorn
    print("--- Starting API Server ---")
    # FIX: Pass the app as an import string to enable reload/workers
    uvicorn.run("api_server:app", host="127.0.0.1", port=8000, reload=True)
