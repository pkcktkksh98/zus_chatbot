import requests
import sqlite3
import os
from bs4 import BeautifulSoup

# Define the source URL and DB path
OUTLETS_URL = "https://zuscoffee.com/category/store/kuala-lumpur-selangor/"
DB_FILE = "zus_outlets.db"



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

        outlet_listings = soup.find_all("article", class_=lambda x: x and "elementor-post" in x) #type:ignore

        if not outlet_listings:
            print("Warning: No outlet listings found.")
            return []

        outlets = []
        for listing in outlet_listings:
            # 1. Get Outlet Name (This selector is fine)
            name_tag = listing.find("p", class_="elementor-heading-title")#type:ignore
            name = name_tag.get_text(strip=True) if name_tag else "N/A"

            # 2. Get Address (--- THIS IS THE FIX ---)
            # # First, find the unique *content* widget box
            address_widget = listing.find("div", class_="elementor-widget-theme-post-content")#type:ignore
            address = "N/A"
            state = "N/A"          

            if address_widget:
                # Second, find the container *inside* that widget
                address_container = address_widget.find("div", class_="elementor-widget-container")#type:ignore
                if address_container:

                    # Third, find the <p> tag *inside* that container
                    address_tag = address_container.find("p")#type:ignore
                    if address_tag:
                        address = address_tag.get_text(strip=True).replace("\n", " ")        #type:ignore              

                        # Basic logic to extract city/state

                        parts = address.split(',')
                        if len(parts) >= 2:
                            last_part = parts[-1].strip().split()
                            if len(last_part) >= 2:
                                state = last_part[-1].strip()
                            elif len(last_part) == 1:
                                state = last_part[0].strip()                      

                        if "Kuala Lumpur" in address:
                            state = "Kuala Lumpur"
                        elif "Selangor" in address:
                            state = "Selangor"           

            # 3. Default Values
            operating_hours = "8:00 AM - 10:00 PM Daily"
            status = "Open"
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
# (This part remains the same as before)
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
        cursor.execute("SELECT name, address, state FROM outlets LIMIT 3")

        for row in cursor.fetchall():
            print(f"Name: {row[0]}\nAddress: {row[1]}\nState: {row[2]}\n")
        conn.close()

    else:
        print("Scraping failed. Cannot set up the database.")