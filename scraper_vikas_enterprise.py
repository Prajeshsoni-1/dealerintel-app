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
MASTER_DB_FILE = "vikas_master_database.csv"

def categorize_title(title):
    title = str(title).strip().upper().replace('-', ' ')
    make, model, variant = "Unknown", "Unknown", "Unknown"
    makes = ['MERCEDES BENZ', 'MARUTI SUZUKI', 'HYUNDAI', 'MAHINDRA', 'TOYOTA', 'HONDA', 
             'TATA', 'KIA', 'MG', 'SKODA', 'VOLKSWAGEN', 'VW', 'RENAULT', 'NISSAN', 
             'JEEP', 'FORD', 'AUDI', 'BMW', 'VOLVO', 'PORSCHE', 'LAND ROVER', 'RANGE ROVER']
    
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
    print("🚀 [STEP 1] BOOTING DYNAMIC PAGINATION SCOUT...")
    car_urls = set()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        try:
            print("[INFO] Loading Vikas Motorland...")
            page.goto("https://www.vikasmotorland.com/buy-used-cars", timeout=60000)
            page.wait_for_timeout(5000)
            
            current_page_num = 1
            empty_attempts = 0
            
            while True:
                links = page.locator("a[href*='/vdp/']").all()
                for link in links:
                    href = link.get_attribute("href")
                    if href:
                        full_url = f"https://www.vikasmotorland.com{href}" if href.startswith('/') else href
                        car_urls.add(full_url)
                
                print(f"[INFO] Page {current_page_num} scanned. Total UNIQUE cars found so far: {len(car_urls)}")
                
                page.mouse.wheel(0, 3000)
                page.wait_for_timeout(2000)
                
                next_page_num = current_page_num + 1
                selectors = [
                    f"a:text-is('{next_page_num}')",
                    f"button:text-is('{next_page_num}')",
                    "a:has-text('Next')",
                    "a:has-text('Load More')",
                    "button.load-more"
                ]
                
                clicked = False
                for selector in selectors:
                    try:
                        if page.locator(selector).count() > 0 and page.locator(selector).first.is_visible():
                            print(f"[INFO] Clicking to Page {next_page_num}...")
                            page.locator(selector).first.click()
                            page.wait_for_timeout(5000)
                            clicked = True
                            current_page_num += 1
                            empty_attempts = 0
                            break
                    except:
                        continue
                        
                if not clicked:
                    empty_attempts += 1
                    if empty_attempts >= 2:
                        print("[INFO] No more pages found. Scout complete!")
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
        print(f"[{i}/{len(car_urls)}] Extracting specs: {url.split('/')[-1]}...")
        html = fetch_secure_html(url)
        if not html: continue
            
        soup = BeautifulSoup(html, 'html.parser')
        
        title_elem = soup.find('h1') or soup.find('h2')
        raw_title = title_elem.get_text(strip=True) if title_elem else "Unknown"
        
        price_raw = 0
        price_match = re.search(r'(?:Price|₹|Rs\.?)\s*([\d,.]+)\s*(Lakhs?|L)?', soup.get_text(), re.IGNORECASE)
        if price_match:
            num_val = float(price_match.group(1).replace(',', ''))
            unit = (price_match.group(2) or "").upper()
            if "LAKH" in unit or "L" == unit: price_raw = int(num_val * 100000)
            else: price_raw = int(num_val)

        text = soup.get_text(separator=' ')
        overview_start = text.find("CAR OVERVIEW")
        overview_text = text[overview_start:text.find("SELLER’S NOTE", overview_start)] if overview_start != -1 else text

        km_match = re.search(r'Kms Done\s*([\d,]+)', overview_text, re.IGNORECASE)
        kilometer = int(km_match.group(1).replace(',', '')) if km_match else 0
        
        year_match = re.search(r'Manufacture Year\s*(\d{4})', overview_text, re.IGNORECASE)
        reg_year = int(year_match.group(1)) if year_match else 0
        
        fuel_match = re.search(r'Fuel Type\s*([A-Za-z]+)', overview_text, re.IGNORECASE)
        fuel = fuel_match.group(1).title() if fuel_match else "Unknown"
        
        trans_match = re.search(r'Transmission\s*([A-Za-z]+)', overview_text, re.IGNORECASE)
        transmission = trans_match.group(1).title() if trans_match else "Unknown"
        
        owner_match = re.search(r'Owner\s*([A-Za-z0-9]+)', overview_text, re.IGNORECASE)
        owner = owner_match.group(1).title() if owner_match else "Unknown"
        
        reg_num_match = re.search(r'Registration Number\s*([A-Z0-9]+)', overview_text, re.IGNORECASE)
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
                "Status": "New", # We default to New, Delta Tracker will correct this
                "Source": "Vikas Motorland"
            })
            
    return pd.DataFrame(final_car_data)

# ==========================================
# 📊 STEP 3: DAILY DELTA TRACKER (NEW/SOLD/ACTIVE)
# ==========================================
def run_delta_tracker(current_df):
    if current_df.empty: 
        print("\n⚠️ [WARN] No cars extracted to track.")
        return
        
    print("\n📊 [STEP 3] RUNNING EXCEL DELTA TRACKER...")
    
    if os.path.exists(MASTER_DB_FILE):
        old_df = pd.read_csv(MASTER_DB_FILE)
        
        # Grab URLs for easy comparison
        old_urls = set(old_df['Detail_URL'].tolist())
        new_urls = set(current_df['Detail_URL'].tolist())
        
        # 1. Update status to 'Active' for cars that still exist
        current_df.loc[current_df['Detail_URL'].isin(old_urls), 'Status'] = 'Active'
        
        # 2. Find Sold cars (in old DB, but not in current scrape)
        sold_urls = old_urls - new_urls
        sold_df = old_df[old_df['Detail_URL'].isin(sold_urls)].copy()
        sold_df['Status'] = 'Sold'
        
        # Combine everything together
        final_df = pd.concat([current_df, sold_df], ignore_index=True)
        
        # Analytics
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
        
        # Make sure Excel is closed before this runs!
        run_delta_tracker(fresh_inventory_df)
    else:
        print("[ERROR] Did not find any URLs during the scout phase.")