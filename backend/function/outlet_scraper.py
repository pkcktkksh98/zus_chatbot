
import requests
import sqlite3
import os
from bs4 import BeautifulSoup

# Define the source URL and DB path
OUTLETS_URL = "https://zuscoffee.com/category/store/kuala-lumpur-selangor/"
# Ensure the DB file is created inside the backend folder
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
        
        # Find all <article> tags that are outlet listings
        outlet_listings = soup.find_all("article", class_=lambda x: x and "elementor-post" in x)
        
        if not outlet_listings:
            print("Warning: No outlet listings found with the <article> selector.")
            return []

        outlets = []
        for listing in outlet_listings:
            name = "N/A"
            address = "N/A"
            state = "N/A"

            # --- 1. Get Outlet Name ---
            # Find the heading tag with the specific 'elementor-heading-title' class
            name_tag = listing.find("h3", class_="elementor-post__title")
            if name_tag and name_tag.find("a"):
                name = name_tag.find("a").get_text(strip=True)
            else:
                # Fallback for other possible tags if structure changes
                name_tag_p = listing.find("p", class_="elementor-heading-title")
                if name_tag_p:
                     name = name_tag_p.get_text(strip=True)


            # --- 2. Get Address ---
            # Find the widget that contains the post content/address
            address_widget = listing.find("div", class_="elementor-widget-theme-post-content")
            if address_widget:
                # The address is usually in the first <p> tag inside this div
                address_tag = address_widget.find("p")
                if address_tag:
                    # Clean up the address text
                    full_address = address_tag.get_text(strip=True).replace("\n", " ").replace("\r", " ")
                    # Remove common unwanted prefixes
                    if full_address.startswith("Address:"):
                        full_address = full_address[8:].strip()
                    address = full_address
                    
                    # --- 3. Determine State (Robust Logic) ---
                    address_lower = address.lower()
                    if "kuala lumpur" in address_lower or " w.p. kuala lumpur" in address_lower:
                        state = "Kuala Lumpur"
                    elif "selangor" in address_lower:
                        state = "Selangor"
                    else:
                        # Attempt to find a 5-digit postcode starting with 4, 5, or 6
                        import re
                        postcode_match = re.search(r'\b([456]\d{4})\b', address)
                        if postcode_match:
                            postcode = postcode_match.group(1)
                            if postcode.startswith('4') or postcode.startswith('6'):
                                state = "Selangor" # High probability
                            elif postcode.startswith('5'):
                                state = "Kuala Lumpur" # High probability
                        else:
                            state = "N/A" # Default if not found

            # 4. Default Values
            operating_hours = "8:00 AM - 10:00 PM Daily"
            status = "Open" 

            # Only add if we successfully found a name and address
            if name != "N/A" and address != "N/A":
                outlets.append((
                    name,
                    address,
                    state,
                    status,
                    operating_hours
                ))
            
            # Print for debugging
            if __name__ == "__main__":
                print(f"Found: Name={name}, State={state}")
            
        print(f"--- Scrape complete. Found and parsed {len(outlets)} valid outlets. ---")
        return outlets

    except requests.exceptions.RequestException as e:
        print(f"Error: Failed to fetch URL. {e}")
        return []
    except Exception as e:
        print(f"An error occurred during scraping: {e}")
        import traceback
        traceback.print_exc()
        return []

# --- Database Ingestion Logic ---

def setup_database(outlets_data):
    """
    Creates the SQLite database and populates it with scraped outlet data.
    """
    # Check if the DB file exists and remove it
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
            print(f"Removed existing database: {DB_FILE}")
        except OSError as e:
            print(f"Error removing database file: {e}. Stopping.")
            return

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

    if not outlets_data:
        print("No outlets data to insert. Database will be empty.")
    else:
        cursor.executany("""
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
            print(f"Name: {row[0]}\nState: {row[2]}\nAddress: {row[1]}\n")
        conn.close()
    else:
        print("Scraping failed or found no data. Database setup skipped.")