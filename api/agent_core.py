import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq #type:ignore
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain.agents.middleware import wrap_tool_call#type:ignore
from langchain_core.messages import ToolMessage

try:
    from .function.tools import all_tools
except ImportError:
    from function.tools import all_tools

# --- 1. Load Environment ---
load_dotenv()
if "GROQ_API_KEY" not in os.environ:
    raise EnvironmentError("GROQ_API_KEY not found in .env file. Please get a free key from console.groq.com")

model ="llama-3.3-70b-versatile"
# --- 2. Setup the LLM (Planner) ---
# As per the docs: pass a model instance to the agent
llm = ChatGroq(
    model=model,
    temperature=0
)

# --- 3. Define Tools (Empty for now) ---
# As per the docs: pass a list of tools.
# The tools are now imported from tools.py
tools = all_tools

@wrap_tool_call
def handle_tool_errors(request, handler):
    """Handle tool execution errors with custom messages."""
    try:
        return handler(request)
    except Exception as e:
        # Return a custom error message to the model
        return ToolMessage(
            content=f"Tool error: Please check your input and try again. ({str(e)})",
            tool_call_id=request.tool_call["id"]
        )
    
# --- 4. Create the Agent (Part 2: Planner Logic) ---
# As per the docs: use create_agent with the model and tools.
# We add a simple system prompt.

system_prompt = (
    "You are a helpful ZUS Coffee assistant. Follow these rules precisely:"
    "1. You have three tools: 'calculator', 'zus_product_information', and 'zus_outlet_database'."
    "2. When the user asks a question, you MUST decide if a tool is needed. "
    "3. If a tool is needed, you will call it. You will receive a tool output (e.g., 'Result: 66' or 'Error: ...' or a JSON blob)."
    "4. **CRITICAL RULE:** After you receive a tool output, your *only* job is to formulate a natural language answer to the user. "
    "   DO NOT call another tool. DO NOT try to re-run the previous tool."
    "5. If a tool returns an error, politely inform the user about the error."
    "6. If the user asks a follow-up question that refers to previous conversation, use the chat history to answer it.")

agent_executor = create_agent(
    model=llm,
    tools=tools,
    middleware=[handle_tool_errors],
    system_prompt=system_prompt
)

# --- 5. Test the Conversation (Part 1: Memory) ---
# --- 5. Test the Conversation (Part 3: Tool Calling) ---
# --- 6. Test the Conversation (Parts 1, 3, 4) ---
def run_conversation_test():
    print("🤖 Bot: Hello! I can help with ZUS outlets, products, and basic math. How can I assist you?\n")

    # We will manually keep track of the history for memory
    chat_history = []

    def ask_question(user_input: str):
        """Helper function to run a turn of the conversation."""
        print(f"👤 User: {user_input}")
        
        # Add human message to history
        chat_history.append(HumanMessage(content=user_input))
        
        # --- FIX 1: Invoke ---
        # Call the agent with the 'messages' key
        response = agent_executor.invoke({
            "messages": chat_history
        })
        
        # --- FIX 2: Append Response ---
        # The agent returns the *entire* history, so we just grab the last message
        ai_response_message = response["messages"][-1]
        chat_history.append(ai_response_message)
        
        # --- FIX 3: Print Content ---
        # Print the .content attribute of the AI message
        print(f"🤖 Bot: {ai_response_message.content}\n")

    # --- Test 1: Part 4 - Text-to-SQL Tool ---
    ask_question("How many outlets are in Kuala Lumpur?'); DROP TABLE outlets; --")

    # # --- Test 2: Part 4 - RAG Tool ---
    ask_question("Do you sell any cups?")

    # --- Test 3: Part 3 - Calculator Tool ---
    ask_question("What is 12 * 5.5?")

    # --- Test 4: Part 1 - Memory Check ---
    ask_question("What was the answer to my first question about outlets?")
    
    # --- Test 5: Part 3 - Unhappy Path (Calculator Error) ---
    ask_question("What is 10 / 0?")

     # --- Check Memory ---
    print("\n--- Final Conversation History (Demonstrating Part 1: Memory) ---")
    for msg in chat_history:
        # Handle cases where the message might be a tool call, not just content
        if isinstance(msg.content, str):
            print(f"[{msg.type.upper()}]: {msg.content}")
        else:
            print(f"[{msg.type.upper()}]: {msg.tool_calls}")

if __name__ == "__main__":
    # NOTE: The bot's answers will be generic (e.g., "I don't have that info")
    # This is EXPECTED. We are only testing Part 1 (memory) and Part 2 (planning).
    run_conversation_test()