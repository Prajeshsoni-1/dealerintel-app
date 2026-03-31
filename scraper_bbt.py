import re
import time
import random
import pandas as pd
from playwright.sync_api import sync_playwright

def categorize_title(title):
    title = str(title).strip().upper().replace('-', ' ')
    make, model, variant = "Unknown", "Unknown", "Unknown"
    
    makes = ['MERCEDES BENZ', 'ROLLS ROYCE', 'ASTON MARTIN', 'LAND ROVER', 'RANGE ROVER', 
             'LAMBORGHINI', 'PORSCHE', 'BENTLEY', 'FERRARI', 'JAGUAR', 'AUDI', 'BMW', 
             'MASERATI', 'LEXUS', 'BUGATTI', 'MCLAREN', 'VOLVO', 'TOYOTA', 'FORD', 'JEEP', 'KIA']
    
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

def run_bbt_multitab_scraper():
    print("🚀 BOOTING BIG BOY TOYZ MULTI-TAB ENGINE V2...")
    final_car_data = []
    
    # The New Radar: Hunts by Hyphen Density and Hidden JSON state
    VISUAL_LINK_FINDER_JS = '''() => {
        let urls = new Set();
        
        // 1. Hyphen Density Radar
        let allLinks = document.querySelectorAll('a');
        for (let a of allLinks) {
            if (!a.href) continue;
            try {
                let urlObj = new URL(a.href, document.baseURI);
                let path = urlObj.pathname;
                let segments = path.split('/').filter(s => s.length > 0);
                if (segments.length > 0) {
                    let lastSegment = segments[segments.length - 1];
                    // Car slugs almost always have 3 or more hyphens
                    if (lastSegment.split('-').length >= 3 || lastSegment.includes('-detail-page')) {
                        if (!path.includes('/blog') && !path.includes('/news')) {
                            urls.add(urlObj.href);
                        }
                    }
                }
            } catch(e) {}
        }
        
        // 2. Next.js Ghost Data Extractor
        try {
            let nextData = document.getElementById('__NEXT_DATA__');
            if (nextData) {
                let matches = nextData.innerText.match(/"slug":"([^"]+)"/g);
                if (matches) {
                    for (let m of matches) {
                        let slug = m.split(':')[1].replace(/"/g, '');
                        if (slug.split('-').length >= 3) {
                            urls.add("https://www.bigboytoyz.com/used-luxury-cars/" + slug + "-detail-page");
                        }
                    }
                }
            }
        } catch(e) {}
        
        return Array.from(urls);
    }'''

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        
        main_page = context.new_page()
        
        try:
            print("[INFO] Loading main grid to scout URLs...")
            main_page.goto("https://www.bigboytoyz.com/collection", timeout=60000)
            main_page.wait_for_timeout(5000)
            
            print("[INFO] Human-like scrolling to load hidden Next.js cars...")
            for _ in range(12):
                main_page.mouse.wheel(0, random.randint(2500, 3500))
                main_page.wait_for_timeout(random.randint(1000, 2000))
                
            car_urls = main_page.evaluate(VISUAL_LINK_FINDER_JS)
            print(f"[SUCCESS] Multi-Tab Engine found {len(car_urls)} cars!")

            for i, url in enumerate(car_urls, 1):
                detail_page = None
                try:
                    display_name = url.split('/')[-1]
                    print(f"[{i}/{len(car_urls)}] Opening New Tab for: {display_name[:30]}...")
                    
                    detail_page = context.new_page()
                    detail_page.goto(url, timeout=45000)
                    detail_page.wait_for_timeout(random.randint(2000, 3500)) 
                    
                    page_text = detail_page.locator("body").inner_text()
                    
                    # Target the Title
                    raw_title = detail_page.title().split('|')[0].strip()
                    if "Big Boy Toyz" in raw_title or len(raw_title) < 5:
                        raw_title = url.split('/')[-1].replace('-1', ' ').replace('-detail-page', '').replace('-', ' ').title()
                    
                    # Expanded Price Target (Looks for ₹, Rs, or Price)
                    price_raw = 0
                    price_match = re.search(r'(?:₹|Rs\.?|Price:?)\s*([\d,.]+)\s*(Lakhs?|L|Crores?|Cr)?', page_text, re.IGNORECASE)
                    if price_match:
                        num_val = float(price_match.group(1).replace(',', ''))
                        unit = (price_match.group(2) or "").upper()
                        if "LAKH" in unit or "L" == unit: price_raw = int(num_val * 100000)
                        elif "CRORE" in unit or "CR" in unit: price_raw = int(num_val * 10000000)
                        else: price_raw = int(num_val)

                    kilometer = 0
                    km_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*(Kms?|Kilometers?)', page_text, re.IGNORECASE)
                    if km_match: kilometer = int(km_match.group(1).replace(',', ''))
                    
                    reg_year = 0
                    year_match = re.search(r'(?:Registration Year|Reg\.?\s*Year|Year)[\s:-]*(\d{4})', page_text, re.IGNORECASE)
                    if year_match: 
                        reg_year = int(year_match.group(1))
                    else:
                        fallback_year = re.search(r'\b(201\d|202\d)\b', page_text)
                        if fallback_year: reg_year = int(fallback_year.group(1))

                    fuel = 'Petrol' if 'petrol' in page_text.lower() else ('Diesel' if 'diesel' in page_text.lower() else ('Electric' if 'electric' in page_text.lower() else 'Unknown'))
                    transmission = 'Automatic' if 'automatic' in page_text.lower() else ('Manual' if 'manual' in page_text.lower() else 'Unknown')
                    
                    owner = "Unknown"
                    owner_match = re.search(r'(?:Owner|Ownership)[\s:-]*([A-Za-z0-9]+)', page_text, re.IGNORECASE)
                    if owner_match: owner = owner_match.group(1).strip()

                    make, model, variant = categorize_title(raw_title)

                    if make != "Unknown":
                        final_car_data.append({
                            "Listing_Title": raw_title, "Make/Brand": make, "Model": model, "Variant": variant, 
                            "Price_Raw": price_raw, "Price": f"₹ {price_raw:,}" if price_raw > 0 else "Unknown", 
                            "Kilometer": kilometer, 
                            "Fuel_Type": fuel, "Transmission": transmission, "Overview_Owner": owner, 
                            "Reg_Year": reg_year, "Detail_URL": url, "Source": "Big Boy Toyz"
                        })
                        
                except Exception as inner_e:
                    print(f"  [WARN] Skipped a car due to error: {inner_e}")
                finally:
                    if detail_page:
                        detail_page.close()
            
            print(f"\n[SUCCESS] Deep extraction complete! Harvested rich data for {len(final_car_data)} luxury cars.")
            
        except Exception as e:
            print(f"[ERROR] Failed to run BBT Scraper: {e}")
            
        browser.close()
        
    df = pd.DataFrame(final_car_data)
    df.to_csv("bbt_inventory.csv", index=False)
    print("💾 Saved directly to bbt_inventory.csv")

if __name__ == "__main__":
    run_bbt_multitab_scraper()