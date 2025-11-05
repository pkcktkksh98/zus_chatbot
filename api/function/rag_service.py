import os
import sqlite3
from typing import Dict, Any

from langchain_community.vectorstores.faiss import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_groq import ChatGroq #type:ignore
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda, RunnableParallel
from langchain_core.output_parsers import StrOutputParser
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent


# Import our scraper
# Note: The relative import '.scraper' only works when running the API server via 'uvicorn api_server:app'
from .scraper import scrape_zus_drinkware
from .outlet_scraper import scrape_outlet_data, setup_database 

from dotenv import load_dotenv
load_dotenv()

if "GROQ_API_KEY" not in os.environ:
    raise EnvironmentError("GROQ_API_KEY not found in .env file.")

model= "llama-3.3-70b-versatile"
FAISS_INDEX_PATH = "faiss_drinkware_index"
SQL_DB_FILE = "zus_outlets.db"
# NOTE: The SQLDatabase connection string must point to the correct file path.
SQL_DATABASE_URI = f"sqlite:///{SQL_DB_FILE}"

# --- Helper Function for DB Setup ---
def ensure_db_is_ready():
    """Checks if DB exists, if not, runs the scraper and setup."""
    if not os.path.exists(SQL_DB_FILE):
        print(f"[{SQL_DB_FILE}] not found. Running scraper and setup...")
        outlets_data = scrape_outlet_data()
        if not outlets_data:
            raise Exception("Failed to scrape outlet data for SQL setup.")
        setup_database(outlets_data)
    else:
        print(f"Found existing database: {SQL_DB_FILE}")

# --- RAG Core Logic ---
# The function MUST be async because it is called with `await` in api_server.py
def initialize_rag_chain():
    """
    Loads or creates the vector store and returns the RAG retrieval chain using LCEL.
    """
    print("Initializing embedding model...")
    # Use a free, fast embedding model
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    vector_store = None
    
    # 1. Load/Create Vector Store (synchronous I/O is fine here)
    if os.path.exists(FAISS_INDEX_PATH):
        print(f"Loading existing vector store from {FAISS_INDEX_PATH}...")
        # Note: LangChain's IO methods here are synchronous and safe
        vector_store = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
    else:
        print("No existing index found. Starting full ingestion...")
        product_data = scrape_zus_drinkware()
        if not product_data:
            raise Exception("Scraping failed. Cannot build vector store.")

        documents = [Document(page_content=item) for item in product_data]
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        splits = text_splitter.split_documents(documents)
        
        print("Creating vector store...")
        vector_store = FAISS.from_documents(splits, embeddings)
        vector_store.save_local(FAISS_INDEX_PATH)
        print(f"Vector store saved to {FAISS_INDEX_PATH}")
    
    print("Vector store loaded.")
    
    # 2. Define Components
    llm = ChatGroq(model=model, temperature=0)
    # The retriever object is synchronous, but the final chain call is async
    retriever = vector_store.as_retriever(search_kwargs={"k": 3})
    
    # Function to format documents for the prompt
    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    # 3. Define the LCEL Prompt
    prompt = ChatPromptTemplate.from_template("""
    You are an assistant for ZUS Coffee. Answer the user's question based ONLY on the following context about drinkware products:
    
    <context>
    {context}
    </context>
    
    Question: {input}
    
    Answer:
    """)

    # -----------------------------------------------------------------
    # The Full RAG Chain: LCEL with Input Mapping
    # This structure is the modern, official way to return both answer and source docs.
    # -----------------------------------------------------------------

    # The chain starts by wrapping the string input in a dict {"input": query}
    rag_chain_final = (
        {"input": RunnablePassthrough()}
        |
        RunnableParallel(
            # Key 1: 'context' - retrieves and formats documents using the 'input' key from the previous step (x['input'])
            context = (lambda x: x['input']) | retriever | RunnableLambda(format_docs),
            
            # Key 2: 'answer' - calculates the final answer.
            # It uses RunnablePassthrough.assign to create the prompt's required input: 
            # {"context": docs_string, "input": original_query}
            answer = RunnablePassthrough.assign(
                context = (lambda x: x['input']) | retriever | RunnableLambda(format_docs)
            ) 
            | prompt 
            | llm 
            | StrOutputParser()
        )
    ).with_types(input_type=str)
    

    print("RAG retrieval chain (LCEL with dict output) created.")
    return rag_chain_final

def initialize_sql_chain():
    """
    Initializes the Text-to-SQL agent for ZUS outlet data.
    """
    print("Initializing SQL agent...")
    
    # 1. Ensure DB exists (scrape/create if necessary)
    ensure_db_is_ready()
    
    # 2. Set up the SQLDatabase connection
    db = SQLDatabase.from_uri(SQL_DATABASE_URI)

    # 3. Initialize the LLM
    llm = ChatGroq(model=model, temperature=0)
    
    # 4. Create the SQL Agent Executor
    # The agent will use the LLM to decide what SQL query to run against the DB.
    sql_agent_executor = create_sql_agent(
        llm=llm,
        db=db,
        agent_type="openai-tools", # A robust agent type
        verbose=False,
        handle_parsing_errors=True,
        # Provide extra context about the tables
        extra_context={
            "table_info": {
                "outlets": "Contains ZUS Coffee outlet information: name, address, city, state (Kuala Lumpur or Selangor), status (Open/Closed), and default operating_hours."
            }
        }
    )
    
    # 5. Create a final Runnable to process the agent's output
    # This runnable takes the user query, runs the SQL agent, and returns the structured output.
    def run_sql_query(query: str) -> Dict[str, Any]:
        """Runs the SQL agent and formats the output."""
        # The agent uses 'input' as the key for the user query
        result = sql_agent_executor.invoke({"input": query})
        
        # The agent output is typically under the 'output' key
        return {
            "query": query,
            "answer": result["output"],
            "raw_sql_agent_response": result 
        }

    # Wrap the function in a RunnableLambda for the API
    sql_chain = RunnableLambda(run_sql_query).with_types(input_type=str)

    print("SQL Agent initialized.")
    return sql_chain

# --- Main Entry Point for the API Server ---

# The API server will call this function during startup to get both chains
async def initialize_chains():
    """Initializes and returns a tuple of (rag_chain, sql_chain)."""
    rag_chain = initialize_rag_chain()
    sql_chain = initialize_sql_chain()
    return rag_chain, sql_chain

# if __name__ == "__main__":
#     # NOTE: The bot's answers will be generic (e.g., "I don't have that info")
#     # This is EXPECTED. We are only testing Part 1 (memory) and Part 2 (planning).
#     initialize_chains()