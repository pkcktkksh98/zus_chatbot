import requests
import sqlite3
import os
from bs4 import BeautifulSoup

# Define the source URL and DB path
OUTLETS_URL = "https://zuscoffee.com/category/store/kuala-lumpur-selangor/"
# Ensure the DB file is created inside the backend folder for consistency
DB_FILE = os.path.join(os.path.dirname(__file__), '..', 'zus_outlets.db')

# --- Scraper Logic ---

def scrape_outlet_data():
    """
    Scrapes ZUS Coffee outlet names and addresses from the target page.
    """
    print(f"--- Starting scrape of outlet locations from: {OUTLETS_URL} ---")
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(OUTLETS_URL, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        outlet_listings = soup.find_all("article", class_=lambda x: x and "elementor-post" in x)
        
        if not outlet_listings:
            print("Warning: No outlet listings found.")
            return []

        outlets = []
        for listing in outlet_listings:
            # 1. Get Outlet Name
            name_tag = listing.find("p", class_="elementor-heading-title")
            name = name_tag.get_text(strip=True) if name_tag else "N/A"

            # 2. Get Address
            address_widget = listing.find("div", class_="elementor-widget-theme-post-content")
            
            address = "N/A"
            state = "N/A"
            
            if address_widget:
                address_container = address_widget.find("div", class_="elementor-widget-container")
                if address_container:
                    address_tag = address_container.find("p")
                    if address_tag:
                        address = address_tag.get_text(strip=True).replace("\n", " ")
                        
                        # --- ROBUST STATE LOGIC FIX ---
                        # Instead of splitting strings, we check for keywords.
                        address_lower = address.lower()
                        if "kuala lumpur" in address_lower or "kl" in address_lower:
                            state = "Kuala Lumpur"
                        elif "selangor" in address_lower:
                            state = "Selangor"
                        else:
                            state = "N/A" # Default if not found
                        # --- END FIX ---

            # 3. Default Values
            operating_hours = "8:00 AM - 10:00 PM Daily"
            status = "Open" 

            # Only print if we are running this script directly (for debugging)
            if __name__ == "__main__":
                 print(f"Name: {name}, State: {state}")
            
            outlets.append((
                name,
                address,
                state,
                status,
                operating_hours
            ))
            
        print(f"--- Scrape complete. Found {len(outlets)} outlets. ---")
        return outlets

    except requests.exceptions.RequestException as e:
        print(f"Error: Failed to fetch URL. {e}")
        return []
    except Exception as e:
        print(f"An error occurred during scraping: {e}")
        return []

# --- Database Ingestion Logic ---

def setup_database(outlets_data):
    """
    Creates the SQLite database and populates it with scraped outlet data.
    """
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print(f"Removed existing database: {DB_FILE}")

    print(f"Creating and populating database: {DB_FILE}...")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS outlets (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            state TEXT NOT NULL,
            status TEXT NOT NULL,
            operating_hours TEXT
        );
    """)

    cursor.executemany("""
        INSERT INTO outlets (name, address, state, status, operating_hours) 
        VALUES (?, ?, ?, ?, ?);
    """, outlets_data)

    conn.commit()
    conn.close()
    
    print(f"Database setup complete. {len(outlets_data)} outlets added.")

if __name__ == "__main__":
    scraped_data = scrape_outlet_data()
    
    if scraped_data:
        setup_database(scraped_data)
        
        print("\n--- Sample data check ---")
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        print("Fetching 3 random samples:")
        cursor.execute("SELECT name, address, state FROM outlets ORDER BY RANDOM() LIMIT 3")
        for row in cursor.fetchall():
            print(f"Name: {row[0]}\nAddress: {row[1]}\nState: {row[2]}\n")
        conn.close()
    else:
        print("Scraping failed. Cannot set up the database.")
