import requests
from langchain_core.tools import tool
from typing import List
import json

# Define the base URL of your locally running FastAPI server
API_BASE_URL = "http://127.0.0.1:8000"

# --- Tool 1: Calculator ---
@tool
def calculator(expression: str) -> str:
    """
    Uses the local /calculate API to perform arithmetic.
    Input should be a simple math expression string, e.g., '2*5 + 10'.
    """
    try:
        response = requests.get(f"{API_BASE_URL}/calculate", params={"expression": expression})
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        # --- FIX IS HERE ---
        data = response.json()
        
        # Check for the expected keys from your FastAPI endpoint
        if data.get("status") == "success" and "result" in data:
            return f"The calculation result is: {data['result']}"
        else:
            # Should catch cases where the API returns a 200 but the body is weird
            return f"Calculation failed: {data.get('detail', 'Unknown error.')}"
        # --- END FIX ---

    except requests.exceptions.HTTPError as e:
        # Handle 400 (Bad Request from our FastAPI endpoint)
        error_detail = e.response.json().get("detail", "Bad Request")
        return f"Tool Error: The expression was invalid. Details: {error_detail}"
    except requests.exceptions.RequestException as e:
        # Handle connection errors (API downtime)
        return f"Tool Error: The Calculator API is unreachable. {e.__class__.__name__}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"

# --- Tool 2: Product RAG ---
@tool
def zus_product_information(query: str) -> str:
    """
    Uses the local /products RAG API to answer questions about ZUS drinkware.
    Input should be a natural language query, e.g., 'Do you sell any cups?'.
    """
    try:
        response = requests.get(f"{API_BASE_URL}/products", params={"query": query})
        response.raise_for_status()
        data = response.json()
        return json.dumps(data) 

    except requests.exceptions.HTTPError as e:
        error_detail = e.response.json().get("detail", "Bad Request")
        return f"Tool Error: The RAG API request failed. Details: {error_detail}"
    except requests.exceptions.RequestException as e:
        return f"Tool Error: The Products API is unreachable. {e.__class__.__name__}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"

# --- Tool 3: Outlet Text-to-SQL ---
@tool
def zus_outlet_database(query: str) -> str:
    """
    Uses the local /outlets Text-to-SQL API to answer questions about ZUS outlets.
    Input should be a natural language query, e.g., 'How many outlets are in Kuala Lumpur?'.
    """
    try:
        response = requests.get(f"{API_BASE_URL}/outlets", params={"query": query})
        response.raise_for_status()
        data = response.json()
        
        # The API already returns a natural language answer
        return data.get('answer', 'No answer found.')

    except requests.exceptions.HTTPError as e:
        error_detail = e.response.json().get("detail", "Bad Request")
        return f"Tool Error: The SQL API request failed. Details: {error_detail}"
    except requests.exceptions.RequestException as e:
        return f"Tool Error: The Outlets API is unreachable. {e.__class__.__name__}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"


# --- Define the LangChain Tool objects ---
all_tools = [calculator, zus_product_information, zus_outlet_database]

