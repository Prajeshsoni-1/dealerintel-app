import os
import re
import time
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ==========================================
# ⚙️ SYSTEM CONFIGURATION
# ==========================================
MASTER_DB_FILE = "cargiant_master_database.csv"
START_URL = "https://cargiant.co.in/stock-cars" 

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
    print("🚀 BOOTING CAR GIANT TURBO ENGINE (HIGH-SPEED MODE)...")
    car_urls = set()
    final_car_data = []

    with sync_playwright() as p:
        # 1. HEADLESS MODE: Runs invisibly for max speed
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080}
        )

        # 2. ASSET BLOCKING: Aborts images, media, and fonts to load pages instantly!
        context.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())

        page = context.new_page()

        # ------------------------------------------
        # STEP 1: HIGH-SPEED GRID SCOUT
        # ------------------------------------------
        print("\n[STEP 1] 🕵️ SCOUTING CAR GIANT GRID...")
        try:
            # wait_until="domcontentloaded" stops waiting for images to load
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
                        if '/car/' in href_lower and not any(bad in href_lower for bad in ['/brand', '/category', '/blog', '/about', '/contact']):
                            full_url = f"https://cargiant.co.in{href}" if href.startswith('/') else href
                            car_urls.add(full_url)
                
                print(f"[INFO] Scanning Grid... Total UNIQUE cars found so far: {len(car_urls)}")
                
                previous_count = len(car_urls)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                page.wait_for_timeout(500) # Reduced scroll wait
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
                    page.wait_for_timeout(1500) # Reduced from 4000 to 1500
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
        # STEP 2: TURBO BROWSER EXTRACTION
        # ------------------------------------------
        if car_urls:
            print(f"\n[STEP 2] ⚡ EXTRACTING {len(car_urls)} CARS DIRECTLY VIA TURBO BROWSER...")
            
            # Record start time to calculate speed
            start_time = time.time()
            
            for i, url in enumerate(car_urls, 1):
                try:
                    display_name = url.split('/')[-1][:30]
                    
                    # Wait_until="domcontentloaded" ignores heavy scripts and images
                    page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    page.mouse.wheel(0, 1000) 
                    page.wait_for_timeout(600) # Micro-wait, drastically reduced from 4000!
                    
                    html_content = page.content()
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # Normalize text
                    text = re.sub(r'\s+', ' ', soup.get_text(separator=' '))
                    
                    raw_title = soup.find('h1').get_text(strip=True) if soup.find('h1') else url.split('/')[-1].replace('-', ' ').title()
                    raw_title = re.sub(r'(?i)Pre Owned\s*', '', raw_title).strip()
                    
                    # 1. PRICE LOGIC
                    valid_prices = []
                    comma_prices = re.findall(r'\b(\d{1,3},\d{2},\d{3})\b', text)
                    for p in comma_prices:
                        try:
                            val = int(p.replace(',', ''))
                            if 100000 <= val <= 300000000: valid_prices.append(val)
                        except: pass
                        
                    word_prices = re.findall(r'(\d{1,3}(?:\.\d{1,2})?)\s*(Lakhs?|Lac|L|Crores?|Cr)\b', text, re.IGNORECASE)
                    for match in word_prices:
                        try:
                            num_val = float(match[0])
                            unit = match[1].upper()
                            if "L" in unit or "LAC" in unit: val = int(num_val * 100000)
                            elif "CR" in unit: val = int(num_val * 10000000)
                            if 100000 <= val <= 300000000: valid_prices.append(val)
                        except: pass
                    
                    price_raw = max(valid_prices) if valid_prices else 0

                    # 2. KM LOGIC
                    kilometer = 0
                    km_match = re.search(r'(?:Kms Done|Kilometer|Kms|Driven)[\s:-]*([\d,]+)', text, re.IGNORECASE)
                    if not km_match: km_match = re.search(r'([\d,]+)\s*(?:kms?|kilometers?)', text, re.IGNORECASE)
                    if km_match: kilometer = int(km_match.group(1).replace(',', ''))

                    # 3. YEAR LOGIC
                    year_match = re.search(r'(?:Reg Year|Model Year|Registration|Mfg Year|Year)[\s:-]*(\d{4})', text, re.IGNORECASE)
                    reg_year = int(year_match.group(1)) if year_match else 0
                    if reg_year == 0:
                        fallback = re.search(r'\b(201\d|202\d)\b', raw_title + " " + text[:500])
                        if fallback: reg_year = int(fallback.group(1))

                    # 4. FUEL & TRANSMISSION
                    fuel = 'Petrol' if 'petrol' in text.lower() else ('Diesel' if 'diesel' in text.lower() else ('Electric' if 'electric' in text.lower() else 'Unknown'))
                    transmission = 'Automatic' if 'automatic' in text.lower() or ' at ' in text.lower() else ('Manual' if 'manual' in text.lower() or ' mt ' in text.lower() else 'Unknown')
                    
                    # 5. OWNER LOGIC
                    owner = "Unknown"
                    owner_match = re.search(r'(?:Ownership|Owner)[\s:-]*(1st|2nd|3rd|first|second)', text, re.IGNORECASE)
                    if owner_match:
                        o = owner_match.group(1).lower()
                        if o in ['1st', 'first']: owner = "First"
                        elif o in ['2nd', 'second']: owner = "Second"
                    
                    # 6. REGISTRATION / STATE
                    registration_number = "Unknown"
                    city = "Unknown"
                    reg_match = re.search(r'(?:Registration)[\s:-]*([A-Z]{2})', text, re.IGNORECASE)
                    if reg_match:
                        registration_number = reg_match.group(1).upper()
                        state_map = {"DL": "Delhi", "HR": "Haryana", "MH": "Maharashtra", "UP": "Uttar Pradesh", "CH": "Chandigarh"}
                        city = state_map.get(registration_number, registration_number)

                    make, model, variant = categorize_title(raw_title)

                    if make != "Unknown" or price_raw > 0:
                        final_car_data.append({
                            "Listing_Title": raw_title, "Make/Brand": make, "Model": model, "Variant": variant.replace(str(reg_year), '').strip(), 
                            "Price_Raw": price_raw, "Price": f"₹ {price_raw:,}" if price_raw > 0 else "Unknown", 
                            "Kilometer": kilometer, "Fuel_Type": fuel, "Transmission": transmission, 
                            "Overview_Owner": owner, "Reg_Year": reg_year, "Age": 2026 - reg_year if reg_year > 0 else 0, 
                            "Registration_Number": registration_number, "City": city, "Detail_URL": url, 
                            "Status": "New", 
                            "Source": "Car Giant"
                        })
                        print(f"  [{i}/{len(car_urls)}] ✅ {make} {model} | ₹ {price_raw:,} | {kilometer:,} km | Owner: {owner}")
                        
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