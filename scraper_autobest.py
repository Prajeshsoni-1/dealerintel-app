import os
import re
import urllib.parse
import requests
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ==========================================
# ⚙️ SYSTEM CONFIGURATION
# ==========================================
SCRAPE_DO_TOKEN = "5aec0b18f44348968429fd336ba6a1f4c545dd2d534"
MASTER_DB_FILE = "autobest_master_database.csv"

def categorize_title(title):
    title = str(title).strip().upper().replace('-', ' ')
    make, model, variant = "Unknown", "Unknown", "Unknown"
    
    makes = ['MERCEDES BENZ', 'ROLLS ROYCE', 'ASTON MARTIN', 'LAND ROVER', 'RANGE ROVER', 
             'LAMBORGHINI', 'PORSCHE', 'BENTLEY', 'FERRARI', 'JAGUAR', 'AUDI', 'BMW', 
             'MASERATI', 'LEXUS', 'BUGATTI', 'MCLAREN', 'VOLVO', 'TOYOTA', 'FORD', 'JEEP', 'MINI']
    
    year_match = re.search(r'^(201\d|202\d)\s+', title)
    if year_match: title = title.replace(year_match.group(0), '')
    
    for m in makes:
        if m in title:
            make = m.title()
            title = title.replace(m, '').strip()
            break
            
    parts = title.split()
    if len(parts) > 0:
        model = parts[0].title()
        variant = " ".join(parts[1:]).title()
            
    return make, model, variant

# ==========================================
# 🕵️ STEP 1: DYNAMIC PAGINATION SCOUT
# ==========================================
def get_all_urls_via_dynamic_clicker():
    print("🚀 [STEP 1] BOOTING AUTOBEST DYNAMIC SCOUT...")
    car_urls = set()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        try:
            print("[INFO] Loading Autobest Emperio...")
            page.goto("https://autobest.co.in/pre-owned-cars", timeout=60000)
            page.wait_for_timeout(5000)
            
            current_page_num = 1
            empty_attempts = 0
            
            while True:
                # 1. Grab all car links using Hyphen Math
                links = page.locator("a").all()
                for link in links:
                    href = link.get_attribute("href")
                    if href:
                        href_lower = href.lower()
                        # SMART FILTER: 3+ hyphens AND no bad keywords
                        if href.count('-') >= 3 and not any(bad_word in href_lower for bad_word in ['/brand', '/category', '/blog', '/about', '/contact']):
                            full_url = f"https://autobest.co.in{href}" if href.startswith('/') else href
                            if "autobest.co.in" in full_url:
                                car_urls.add(full_url)
                
                print(f"[INFO] View {current_page_num} scanned. Total UNIQUE cars found so far: {len(car_urls)}")
                
                # 2. Scroll to bottom
                page.mouse.wheel(0, 3000)
                page.wait_for_timeout(2500)
                
                # 3. Find and click "Next" or "Load More"
                next_page_num = current_page_num + 1
                selectors = [
                    "button:has-text('Load More')",
                    "a:has-text('Load More')",
                    "button:has-text('View More')",
                    "a:has-text('Next')",
                    f"button:text-is('{next_page_num}')",
                    f"a:text-is('{next_page_num}')",
                ]
                
                clicked = False
                for selector in selectors:
                    try:
                        if page.locator(selector).count() > 0 and page.locator(selector).first.is_visible():
                            print(f"[INFO] Clicking to load more inventory...")
                            page.locator(selector).first.click()
                            page.wait_for_timeout(4000)
                            clicked = True
                            current_page_num += 1
                            empty_attempts = 0
                            break
                    except:
                        continue
                        
                if not clicked:
                    empty_attempts += 1
                    if empty_attempts >= 2:
                        print("[INFO] Reached the end of the inventory. Scout complete!")
                        break

        except Exception as e:
            print(f"[ERROR] Dynamic Scout failed: {e}")
            
        browser.close()
        
    return list(car_urls)

# ==========================================
# 🛡️ STEP 2: PROXY SHIELD EXTRACTION
# ==========================================
def fetch_secure_html(target_url):
    encoded_url = urllib.parse.quote(target_url)
    proxy_url = f"http://api.scrape.do/?token={SCRAPE_DO_TOKEN}&url={encoded_url}"
    try:
        response = requests.get(proxy_url, timeout=45)
        if response.status_code == 200: return response.text
    except: pass
    return None

def extract_all_cars(car_urls):
    print(f"\n⚡ [STEP 2] SURGICAL EXTRACTION OF {len(car_urls)} CARS VIA PROXY SHIELD...")
    final_car_data = []

    for i, url in enumerate(car_urls, 1):
        print(f"[{i}/{len(car_urls)}] Extracting specs: {url.split('/')[-1][:30]}...")
        html = fetch_secure_html(url)
        if not html: continue
            
        soup = BeautifulSoup(html, 'html.parser')
        
        title_elem = soup.find('h1') or soup.find('h2')
        raw_title = title_elem.get_text(strip=True) if title_elem else url.split('/')[-1].replace('-', ' ').title()
        
        # FAULT-TOLERANT PRICE EXTRACTION
        price_raw = 0
        price_match = re.search(r'(?:Price|₹|Rs\.?)\s*([\d,.]+)\s*(Lakhs?|L|Crores?|Cr)?', soup.get_text(), re.IGNORECASE)
        if price_match:
            try:
                num_val = float(price_match.group(1).replace(',', ''))
                unit = (price_match.group(2) or "").upper()
                if "LAKH" in unit or "L" == unit: price_raw = int(num_val * 100000)
                elif "CRORE" in unit or "CR" in unit: price_raw = int(num_val * 10000000)
                else: price_raw = int(num_val)
            except ValueError:
                price_raw = 0

        text = soup.get_text(separator=' ')

        km_match = re.search(r'(?:Kms Done|Kilometers|Kms?|Driven)\s*[:\-]?\s*([\d,]+)', text, re.IGNORECASE)
        kilometer = int(km_match.group(1).replace(',', '')) if km_match else 0
        
        year_match = re.search(r'(?:Manufacture Year|Registration Year|Reg\.?\s*Year|Year|Mfg Year)[\s:-]*(\d{4})', text, re.IGNORECASE)
        reg_year = int(year_match.group(1)) if year_match else 0
        if reg_year == 0:
            fallback = re.search(r'\b(201\d|202\d)\b', raw_title)
            if fallback: reg_year = int(fallback.group(1))
            
        fuel_match = re.search(r'(?:Fuel Type|Fuel)\s*[:\-]?\s*([A-Za-z]+)', text, re.IGNORECASE)
        fuel = fuel_match.group(1).title() if fuel_match else "Unknown"
        
        trans_match = re.search(r'Transmission\s*[:\-]?\s*([A-Za-z]+)', text, re.IGNORECASE)
        transmission = trans_match.group(1).title() if trans_match else "Unknown"
        
        owner_match = re.search(r'(?:Owner|Ownership)\s*[:\-]?\s*([1-9]|First|Second|Third)', text, re.IGNORECASE)
        owner = owner_match.group(1).title() if owner_match else "Unknown"
        
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
                "Source": "Autobest Emperio"
            })
            
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
    car_urls = get_all_urls_via_dynamic_clicker()
    
    if car_urls:
        fresh_inventory_df = extract_all_cars(car_urls)
        run_delta_tracker(fresh_inventory_df)
    else:
        print("[ERROR] Did not find any URLs during the scout phase.")