import requests
from bs4 import BeautifulSoup#type:ignore

# The URL we need to scrape
DRINKWARE_URL = "https://shop.zuscoffee.com/collections/drinkware"

def scrape_zus_drinkware():
    """
    Scrapes the ZUS Coffee drinkware page for product names and descriptions.
    """
    print(f"--- Starting scrape of {DRINKWARE_URL} ---")
    
    try:
        # 1. Fetch the HTML content
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
        }
        response = requests.get(DRINKWARE_URL, headers=headers)
        response.raise_for_status()

        # 2. Parse the HTML with BeautifulSoup
        soup = BeautifulSoup(response.content, "html.parser")

        # 3. Find the products
        product_cards = soup.find_all("product-card", class_="product-card")
        
        if not product_cards:
            print("Warning: No products found. The website's class names may have changed.")
            return []

        products = []
        for card in product_cards:
            # --- UPDATED NAME LOGIC ---
            name = "No Name"
            name_tag = card.find("span", class_="product-card__title")
            if name_tag:
                name_anchor = name_tag.find("a") # Find the <a> tag inside the <span>
                if name_anchor:
                    name = name_anchor.get_text(strip=True)
            
            # --- UPDATED PRICE LOGIC (Robust) ---
            price = "No Price"
            price_list = card.find("price-list") # Find the price container
            
            if price_list:
                # First, try to find the "sale-price" tag
                sale_price_tag = price_list.find("sale-price") # <-- 1. CLASS FIX
                
                if sale_price_tag:
                    # 2. REMOVE the hidden "Sale price" span
                    if sale_price_tag.find("span", class_="sr-only"):
                        sale_price_tag.find("span", class_="sr-only").decompose() 
                    
                    price = sale_price_tag.get_text(strip=True)
                else:
                    # If no sale price, look for the "regular-price"
                    regular_price_tag = price_list.find("compare-at-price", class_="text-subdued line-through")
                    if regular_price_tag:
                        if regular_price_tag.find("span", class_="sr-only"):
                            regular_price_tag.find("span", class_="sr-only").decompose() 
            
            # 3. CLEAN quotes, "RM", and spaces
            price_cleaned = price.replace("RM", "RM ").replace('"', '').strip()

            # Create a simple text representation
            product_text = f"Product: {name}\nPrice: {price_cleaned}\n"
            products.append(product_text)
            
        print(f"--- Scrape complete. Found {len(products)} products. ---")
        return products

    except requests.exceptions.RequestException as e:
        print(f"Error: Failed to fetch URL. {e}")
        return []
    except Exception as e:
        print(f"An error occurred during scraping: {e}")
        return []

if __name__ == "__main__":
    # This allows us to run this file directly to test the scraper
    product_data = scrape_zus_drinkware()
    if product_data:
        print("\n--- Sample Product Data ---")
        for item in product_data: 
            print(item)
    else:
        print("No product data was scraped.")