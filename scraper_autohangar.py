import os
import re
import time
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ==========================================
# ⚙️ SYSTEM CONFIGURATION
# ==========================================
MASTER_DB_FILE = "autohangar_master_database.csv"
START_URL = "https://www.autohangaradvantage.com/buy-a-car" 

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
# 🚀 100% PLAYWRIGHT ENTERPRISE ENGINE
# ==========================================
def run_full_playwright_scraper():
    print("🚀 BOOTING 100% PLAYWRIGHT ENTERPRISE ENGINE (AUTO HANGAR)...")
    car_urls = set()
    final_car_data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        # ------------------------------------------
        # STEP 1: FORCE-CLICK JS SCOUT
        # ------------------------------------------
        print("\n[STEP 1] 🕵️ SCOUTING INVENTORY...")
        try:
            page.goto(START_URL, timeout=60000)
            page.wait_for_timeout(5000)
            
            try: page.keyboard.press("Escape")
            except: pass

            empty_scrolls = 0
            while True:
                links = page.locator("a").all()
                for link in links:
                    href = link.get_attribute("href")
                    if href:
                        href_lower = href.lower()
                        if href.count('-') >= 3 and not any(bad in href_lower for bad in ['/brand', '/category', '/blog', '/about', '/contact', '/privacy']):
                            full_url = f"https://www.autohangaradvantage.com{href}" if href.startswith('/') else href
                            car_urls.add(full_url)
                
                print(f"[INFO] Scanning Grid... Total UNIQUE cars found so far: {len(car_urls)}")
                
                previous_count = len(car_urls)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                page.wait_for_timeout(2000)
                page.mouse.wheel(0, -600) 
                page.wait_for_timeout(1000)
                
                js_click_code = """
                let buttons = document.querySelectorAll('button, a');
                let clicked = false;
                for(let b of buttons) {
                    if(b.innerText && b.innerText.toLowerCase().includes('load more')) {
                        b.click();
                        clicked = true;
                        break;
                    }
                }
                clicked;
                """
                clicked = page.evaluate(js_click_code)
                
                if clicked:
                    page.wait_for_timeout(4000)
                    empty_scrolls = 0
                else:
                    empty_scrolls += 1
                    
                if empty_scrolls >= 3:
                    print(f"[SUCCESS] Reached the end of the inventory. Found {len(car_urls)} cars total!")
                    break

        except Exception as e:
            print(f"[ERROR] Scout failed: {e}")

        car_urls = list(car_urls)

        # ------------------------------------------
        # STEP 2: HIGH-ACCURACY EXTRACTION
        # ------------------------------------------
        if car_urls:
            print(f"\n[STEP 2] ⚡ EXTRACTING {len(car_urls)} CARS DIRECTLY VIA BROWSER...")
            for i, url in enumerate(car_urls, 1):
                try:
                    display_name = url.split('/')[-1][:30]
                    print(f"[{i}/{len(car_urls)}] Extracting: {display_name}...")
                    
                    page.goto(url, timeout=60000)
                    page.wait_for_timeout(4000)
                    page.mouse.wheel(0, 800)
                    page.wait_for_timeout(1500)
                    
                    html_content = page.content()
                    soup = BeautifulSoup(html_content, 'html.parser')
                    text = soup.get_text(separator=' ')
                    
                    raw_title = soup.find('h1').get_text(strip=True) if soup.find('h1') else url.split('/')[-1].replace('-', ' ').title()
                    
                    # 1. PRICE LOGIC: The First Realistic Price Fix
                    valid_prices = []
                    price_matches = re.findall(r'(?:₹|rs\.?|inr|price:?)\s*([\d,.]+)\s*(lakhs?|lac|l|crores?|cr)?', text, re.IGNORECASE)
                    for match in price_matches:
                        try:
                            num_str = match[0].replace(',', '')
                            if not num_str: continue
                            num_val = float(num_str)
                            unit = (match[1] or "").upper()
                            if "LAKH" in unit or "LAC" in unit or "L" == unit: val = int(num_val * 100000)
                            elif "CRORE" in unit or "CR" in unit: val = int(num_val * 10000000)
                            else: val = int(num_val)
                            
                            # MUST be between 1 Lakh and 15 Crore to be considered a real car price!
                            if 100000 <= val <= 150000000:
                                valid_prices.append(val)
                        except: pass
                    
                    # We take the FIRST valid price on the page (always the one at the top near the title)
                    price_raw = valid_prices[0] if valid_prices else 0

                    # 2. KM LOGIC (Captures backwards and forwards)
                    kilometer = 0
                    km_match = re.search(r'([\d,]+)\s*(?:kms?|kilometers?)|(?:kms?|kilometers?|driven|mileage|odometer)[\s:-]*([\d,]+)', text, re.IGNORECASE)
                    if km_match:
                        km_str = km_match.group(1) if km_match.group(1) else km_match.group(2)
                        kilometer = int(km_str.replace(',', ''))

                    # 3. YEAR LOGIC
                    year_match = re.search(r'(?:year|mfg|reg|model|registration)[\s:-]*(\d{4})', text, re.IGNORECASE)
                    reg_year = int(year_match.group(1)) if year_match else 0
                    if reg_year == 0:
                        fallback = re.search(r'\b(201\d|202\d)\b', raw_title)
                        if fallback: reg_year = int(fallback.group(1))

                    # 4. FUEL & TRANSMISSION
                    fuel = 'Petrol' if 'petrol' in text.lower() else ('Diesel' if 'diesel' in text.lower() else ('Electric' if 'electric' in text.lower() else 'Unknown'))
                    
                    transmission = 'Unknown'
                    if re.search(r'\b(automatic|at)\b', text, re.IGNORECASE): transmission = 'Automatic'
                    elif re.search(r'\b(manual|mt)\b', text, re.IGNORECASE): transmission = 'Manual'
                    
                    # 5. OWNER LOGIC
                    owner = "Unknown"
                    owner_match = re.search(r'(?:owner|ownership)\s*[:\-]?\s*([1-9]|first|second|third|1st|2nd|3rd)', text, re.IGNORECASE)
                    owner_reverse = re.search(r'(1st|2nd|3rd|first|second)\s*owner', text, re.IGNORECASE)
                    if owner_match:
                        o = owner_match.group(1).lower()
                        if o in ['1', '1st', 'first']: owner = "First"
                        elif o in ['2', '2nd', 'second']: owner = "Second"
                    elif owner_reverse:
                        o = owner_reverse.group(1).lower()
                        if o in ['1st', 'first']: owner = "First"
                        elif o in ['2nd', 'second']: owner = "Second"
                    
                    # 6. REGISTRATION / CITY
                    reg_num_match = re.search(r'Registration Number\s*([A-Z0-9]+)', text, re.IGNORECASE)
                    registration_number = reg_num_match.group(1).upper() if reg_num_match else "Unknown"
                    city = "Unknown"
                    if registration_number != "Unknown":
                        rto_match = re.match(r'([A-Z]{2}\d{1,2})', registration_number)
                        if rto_match: city = rto_match.group(1)

                    make, model, variant = categorize_title(raw_title)

                    if make != "Unknown" or price_raw > 0:
                        final_car_data.append({
                            "Listing_Title": raw_title, "Make/Brand": make, "Model": model, "Variant": variant.replace(str(reg_year), '').strip(), 
                            "Price_Raw": price_raw, "Price": f"₹ {price_raw:,}" if price_raw > 0 else "Unknown", 
                            "Kilometer": kilometer, "Fuel_Type": fuel, "Transmission": transmission, 
                            "Overview_Owner": owner, "Reg_Year": reg_year, "Age": 2026 - reg_year if reg_year > 0 else 0, 
                            "Registration_Number": registration_number, "City": city, "Detail_URL": url, 
                            "Status": "New", 
                            "Source": "Auto Hangar Advantage"
                        })
                        print(f"  ✅ Extracted: {make} {model} | ₹ {price_raw:,} | {kilometer:,} km | {transmission}")
                        
                except Exception as inner_e:
                    print(f"  [WARN] Skipped a car due to error: {inner_e}")
                    
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