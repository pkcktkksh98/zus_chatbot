import os
import json
import ast
from dotenv import load_dotenv
from langchain_groq import ChatGroq #type:ignore
from langchain.agents import create_agent
from langchain_core.messages import ToolMessage
from langchain.agents.middleware import wrap_tool_call #type:ignore
from langchain_core.tools import Tool # We will create tools manually
from langchain_core.runnables import Runnable

# --- Load Environment & Config ---
load_dotenv()
if "GROQ_API_KEY" not in os.environ:
    raise EnvironmentError("GROQ_API_KEY not found in .env file.")

MODEL_NAME = "llama-3.3-70b-versatile" # Use the smart 70b model

# --- Helper function for Calculator tool ---
def safe_eval(expression: str) -> float:
    """Safely evaluates a simple mathematical expression."""
    tree = ast.parse(expression, mode='eval')
    allowed_nodes = {
        ast.Expression, ast.Call, ast.Name, ast.Load,
        ast.BinOp, ast.UnaryOp, ast.Num, ast.Constant,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd
    }
    for node in ast.walk(tree):
        if type(node) not in allowed_nodes:
            raise ValueError(f"Disallowed operation in expression: {type(node).__name__}")
    return eval(compile(tree, "<string>", "eval"), {}, {})

# --- Define Error Handling Middleware ---
@wrap_tool_call
def handle_tool_errors(request, handler):
    """Handle tool execution errors with custom messages."""
    try:
        # handler is the tool function (e.g., rag_chain.invoke)
        return handler(request)
    except Exception as e:
        return ToolMessage(
            content=f"Tool error: Please check your input and try again. ({str(e)})",
            tool_call_id=request.tool_call["id"]
        )

# --- Main Agent Initialization Function ---
def initialize_agent_executor(rag_chain: Runnable, sql_chain: Runnable):
    """
    Creates and returns the main agent executor.
    It now RECEIVES the RAG and SQL chains to use them directly.
    """
    print("Initializing main agent executor with direct-call tools...")
    
    llm = ChatGroq(
        model=MODEL_NAME,
        temperature=0
    )
    
    # --- Tool 1: Calculator Tool (Direct Call) ---
    def calculator_func(expression: str) -> str:
        try:
            result = safe_eval(expression)
            return f"Result: {result}"
        except Exception as e:
            return f"Error: {str(e)}"

    calculator_tool = Tool(
        name="calculator",
        func=calculator_func,
        description="A useful tool for performing simple arithmetic operations. Input must be a mathematical expression string, e.g., '15*2 - 4'."
    )
    
    # --- Tool 2: RAG Tool (Direct Call) ---
    def rag_tool_func(query: str) -> str:
        try:
            # We call the chain's .invoke() method directly!
            result = rag_chain.invoke(query)
            # result is {"answer": "...", "context": "..."}
            return json.dumps(result) # Return the raw JSON for the agent
        except Exception as e:
            return f"Error: {str(e)}"

    rag_tool = Tool(
        name="zus_product_information",
        func=rag_tool_func,
        description="Use this tool to answer questions about ZUS Coffee drinkware products, such as cups, tumblers, or bottles. Input is a natural language question."
    )
    
    # --- Tool 3: SQL Tool (Direct Call) ---
    def sql_tool_func(query: str) -> str:
        try:
            # We call the chain's .invoke() method directly!
            result = sql_chain.invoke(query)
            # result is {"answer": "..."}
            return result.get('answer', 'No answer found.')
        except Exception as e:
            return f"Error: {str(e)}"
            
    sql_tool = Tool(
        name="zus_outlet_database",
        func=sql_tool_func,
        description="Use this tool to answer questions about ZUS Coffee outlet locations, addresses, states, and operating hours. Input is a natural language question."
    )
    
    # --- All tools list ---
    tools = [calculator_tool, rag_tool, sql_tool]
    
    # The strict, rules-based prompt
    system_prompt = (
        "You are a helpful ZUS Coffee assistant. Follow these rules precisely:"
        "1. You have three tools: 'calculator', 'zus_product_information', and 'zus_outlet_database'."
        "2. When the user asks a question, you MUST decide if a tool is needed. "
        "3. If a tool is needed, you will call it. You will receive a tool output."
        "4. **CRITICAL RULE:** After you receive a tool output, your *only* job is to formulate a natural language answer to the user. "
        "   DO NOT call another tool."
        "5. If a tool returns an error, politely inform the user about the error, using the error message provided."
    )

    agent_executor = create_agent(
        model=llm,
        tools=tools,
        middleware=[handle_tool_errors],
        system_prompt=system_prompt
    )
    
    print("Agent executor successfully built with direct-call tools.")
    return agent_executor

