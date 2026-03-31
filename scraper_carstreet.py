import os
import re
import time
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ==========================================
# ⚙️ SYSTEM CONFIGURATION
# ==========================================
MASTER_DB_FILE = "carstreet_master_database.csv"
START_URL = "https://www.carstreetindia.com/car-stock.htm" 

def categorize_title(title):
    title = str(title).strip().upper().replace('-', ' ')
    make, model, variant = "Unknown", "Unknown", "Unknown"
    
    makes = ['MERCEDES BENZ', 'MERCEDES-BENZ', 'ROLLS ROYCE', 'ASTON MARTIN', 'LAND ROVER', 'RANGE ROVER', 
             'LAMBORGHINI', 'PORSCHE', 'BENTLEY', 'FERRARI', 'JAGUAR', 'AUDI', 'BMW', 
             'MASERATI', 'LEXUS', 'BUGATTI', 'MCLAREN', 'VOLVO', 'TOYOTA', 'FORD', 'JEEP', 'MINI']
    
    year_match = re.search(r'^(201\d|202\d)\s+', title)
    if year_match: title = title.replace(year_match.group(0), '')
    
    for m in makes:
        if m in title:
            make = "Mercedes Benz" if m in ["MERCEDES-BENZ", "MERCEDES BENZ"] else m.title()
            title = title.replace(m, '').strip()
            break
            
    parts = title.split()
    if len(parts) > 0:
        model = parts[0].title()
        variant = " ".join(parts[1:]).title()
            
    return make, model, variant

# ==========================================
# 🚀 100% PLAYWRIGHT TURBO ENGINE
# ==========================================
def run_full_playwright_scraper():
    print("🚀 BOOTING CAR STREET TURBO ENGINE (DEEP TABLE PARSER)...")
    car_urls = set()
    final_car_data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        context.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())
        page = context.new_page()

        # ------------------------------------------
        # STEP 1: STRICT SCOUTING (NO WHATSAPP LINKS)
        # ------------------------------------------
        print("\n[STEP 1] 🕵️ SCOUTING CAR STREET GRID...")
        try:
            page.goto(START_URL, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            
            try: page.keyboard.press("Escape")
            except: pass

            empty_scrolls = 0
            while True:
                links = page.locator("a").all()
                for link in links:
                    href = link.get_attribute("href")
                    if href:
                        href_lower = href.lower()
                        # Strict Car Filter: Bypasses WhatsApp and Category pages
                        if '/car/' in href_lower and '.htm' in href_lower and 'whatsapp' not in href_lower and 'facebook' not in href_lower:
                            if not any(bad in href_lower for bad in ['/brand', '/category', '/blog', '/about', '/contact', '/services']):
                                full_url = f"https://www.carstreetindia.com{href}" if href.startswith('/') else href
                                car_urls.add(full_url)
                
                print(f"[INFO] Scanning Grid... Total UNIQUE cars found so far: {len(car_urls)}")
                
                previous_count = len(car_urls)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                page.wait_for_timeout(500) 
                page.mouse.wheel(0, -600) 
                page.wait_for_timeout(500)
                
                js_click_code = """
                let buttons = document.querySelectorAll('button, a, .page-link, .pagination-item, .next');
                let clicked = false;
                for(let b of buttons) {
                    let text = (b.innerText || "").toLowerCase().trim();
                    if(text.includes('load more') || text.includes('next') || text === '>' || text === '»') {
                        b.click();
                        clicked = true;
                        break;
                    }
                }
                clicked;
                """
                clicked = page.evaluate(js_click_code)
                
                if clicked:
                    page.wait_for_timeout(1500)
                    empty_scrolls = 0
                else:
                    empty_scrolls += 1
                    
                if empty_scrolls >= 3 and len(car_urls) == previous_count:
                    print(f"[SUCCESS] Reached the end of the inventory. Found {len(car_urls)} cars total!")
                    break

        except Exception as e:
            print(f"[ERROR] Scout failed: {e}")

        car_urls = list(car_urls)

        # ------------------------------------------
        # STEP 2: DEEP DOM TABLE EXTRACTION
        # ------------------------------------------
        if car_urls:
            print(f"\n[STEP 2] ⚡ EXTRACTING {len(car_urls)} CARS VIA DEEP SPEC PARSER...")
            start_time = time.time()
            
            for i, url in enumerate(car_urls, 1):
                try:
                    display_name = url.split('/')[-1][:30]
                    
                    page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(500) 
                    page.mouse.wheel(0, 1000)
                    page.wait_for_timeout(500)
                    
                    html_content = page.content()
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # 1. DIRECT DOM-NODE PARSER (Reads the table exactly like your screenshot)
                    text_blocks = list(soup.stripped_strings)
                    specs = {}
                    
                    for idx, block in enumerate(text_blocks):
                        b_lower = block.lower().strip()
                        if b_lower == 'reg. year' and idx + 1 < len(text_blocks): specs['Reg_Year'] = text_blocks[idx+1]
                        elif b_lower == 'make year' and idx + 1 < len(text_blocks): specs['Make_Year'] = text_blocks[idx+1]
                        elif b_lower == 'km driven' and idx + 1 < len(text_blocks): specs['KM'] = text_blocks[idx+1]
                        elif b_lower == 'fuel type' and idx + 1 < len(text_blocks): specs['Fuel'] = text_blocks[idx+1]
                        elif b_lower == 'transmission' and idx + 1 < len(text_blocks): specs['Transmission'] = text_blocks[idx+1]
                        elif b_lower == 'no. of owner' and idx + 1 < len(text_blocks): specs['Owner'] = text_blocks[idx+1]
                        elif b_lower == 'colour' and idx + 1 < len(text_blocks): specs['Colour'] = text_blocks[idx+1]
                        elif b_lower == 'reg. state' and idx + 1 < len(text_blocks): specs['State'] = text_blocks[idx+1]
                        elif b_lower in ['milege', 'mileage'] and idx + 1 < len(text_blocks): specs['Mileage'] = text_blocks[idx+1]
                        elif b_lower == 'top speed' and idx + 1 < len(text_blocks): specs['Top_Speed'] = text_blocks[idx+1]

                    # 2. DATA FORMATTING
                    raw_title = url.split('/')[-1].split('_')[0].replace('-', ' ').title()
                    raw_title = re.sub(r'(?i)Pre Owned\s*', '', raw_title).strip()
                    
                    kilometer = int(re.sub(r'[^\d]', '', specs.get('KM', '0')) or 0)
                    
                    reg_year_str = specs.get('Reg_Year', '0')
                    reg_year_match = re.search(r'(\d{4})', reg_year_str)
                    reg_year = int(reg_year_match.group(1)) if reg_year_match else 0
                    
                    make_year_str = specs.get('Make_Year', '0')
                    make_year_match = re.search(r'(\d{4})', make_year_str)
                    make_year = int(make_year_match.group(1)) if make_year_match else 0
                    
                    fuel = specs.get('Fuel', 'Unknown').title()
                    transmission = specs.get('Transmission', 'Unknown').title()
                    
                    owner_raw = specs.get('Owner', 'Unknown').lower()
                    owner = "First" if '1' in owner_raw or 'first' in owner_raw else ("Second" if '2' in owner_raw or 'second' in owner_raw else "Unknown")
                    
                    colour = specs.get('Colour', 'Unknown').title()
                    state = specs.get('State', 'Unknown').title()
                    mileage = specs.get('Mileage', 'Unknown')
                    top_speed = specs.get('Top_Speed', 'Unknown')

                    # 3. PRICE EXTRACTION (Bypassing the 8500000 EMI trap)
                    full_text = " ".join(text_blocks)
                    valid_prices = []
                    
                    comma_prices = re.findall(r'\b(\d{1,3},\d{2},\d{3})\b', full_text)
                    for p in comma_prices:
                        try:
                            val = int(p.replace(',', ''))
                            if 100000 <= val <= 300000000 and val != 8500000: valid_prices.append(val)
                        except: pass
                        
                    word_prices = re.findall(r'(\d{1,3}(?:\.\d{1,2})?)\s*(Lakhs?|Lac|L|Crores?|Cr)\b', full_text, re.IGNORECASE)
                    for match in word_prices:
                        try:
                            num_val = float(match[0])
                            unit = match[1].upper()
                            if "L" in unit or "LAC" in unit: val = int(num_val * 100000)
                            elif "CR" in unit: val = int(num_val * 10000000)
                            if 100000 <= val <= 300000000 and val != 8500000: valid_prices.append(val)
                        except: pass
                    
                    price_raw = max(valid_prices) if valid_prices else 0

                    make, model, variant = categorize_title(raw_title)

                    if make != "Unknown" or price_raw > 0:
                        final_car_data.append({
                            "Listing_Title": raw_title, "Make/Brand": make, "Model": model, "Variant": variant.replace(str(reg_year), '').strip(), 
                            "Price_Raw": price_raw, "Price": f"₹ {price_raw:,}" if price_raw > 0 else "Unknown", 
                            "Kilometer": kilometer, "Fuel_Type": fuel, "Transmission": transmission, 
                            "Overview_Owner": owner, "Colour": colour, "Mileage": mileage, "Top_Speed": top_speed,
                            "Make_Year": make_year, "Reg_Year": reg_year, "Age": 2026 - reg_year if reg_year > 0 else 0, 
                            "Registration_Number": "Unknown", "State": state, "Detail_URL": url, 
                            "Status": "New", 
                            "Source": "Car Street India"
                        })
                        print(f"  [{i}/{len(car_urls)}] ✅ {make} {model} | ₹ {price_raw:,} | {kilometer:,} km | Owner: {owner} | State: {state} | Color: {colour}")
                        
                except Exception as inner_e:
                    print(f"  [WARN] Skipped a car due to error: {inner_e}")
            
            end_time = time.time()
            print(f"\n[INFO] ⏱️ Extraction completed in {round((end_time - start_time) / 60, 2)} minutes!")
                    
        browser.close()
        return pd.DataFrame(final_car_data)

# ==========================================
# 📊 STEP 3: DAILY DELTA TRACKER
# ==========================================
def run_delta_tracker(current_df):
    if current_df.empty: 
        print("\n⚠️ [WARN] No cars extracted to track.")
        return
        
    print("\n📊 [STEP 3] RUNNING EXCEL DELTA TRACKER...")
    
    if os.path.exists(MASTER_DB_FILE):
        old_df = pd.read_csv(MASTER_DB_FILE)
        
        old_urls = set(old_df['Detail_URL'].tolist())
        new_urls = set(current_df['Detail_URL'].tolist())
        
        current_df.loc[current_df['Detail_URL'].isin(old_urls), 'Status'] = 'Active'
        
        sold_urls = old_urls - new_urls
        sold_df = old_df[old_df['Detail_URL'].isin(sold_urls)].copy()
        sold_df['Status'] = 'Sold'
        
        final_df = pd.concat([current_df, sold_df], ignore_index=True)
        
        new_count = len(current_df[current_df['Status'] == 'New'])
        active_count = len(current_df[current_df['Status'] == 'Active'])
        sold_count = len(sold_urls)
        
        print(f"[INFO] 📈 Market Update:")
        print(f"       🟢 NEW Listings: {new_count}")
        print(f"       🔵 ACTIVE Listings: {active_count}")
        print(f"       🔴 SOLD Listings: {sold_count}")
    else:
        print("[INFO] No previous database found. Creating Baseline. All cars marked as 'New'.")
        final_df = current_df
        
    try:
        final_df.to_csv(MASTER_DB_FILE, index=False)
        print(f"✅ [SUCCESS] Master Database Updated! Saved to {MASTER_DB_FILE}.")
    except Exception as e:
        print(f"❌ [ERROR] Could not save master database. Is Excel open? Error: {e}")

if __name__ == "__main__":
    fresh_inventory_df = run_full_playwright_scraper()
    if fresh_inventory_df is not None and not fresh_inventory_df.empty:
        run_delta_tracker(fresh_inventory_df)