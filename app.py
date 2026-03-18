import streamlit as st
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from seleniumbase import Driver
import time
import re
import os
import plotly.express as px
from datetime import datetime
from supabase import create_client, Client

# ==========================================
# 🚀 1. UI & BRANDING CONFIGURATION
# ==========================================
st.set_page_config(page_title="DealerIntel AI | Procurement", page_icon="🌐", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    div[data-testid="stMetric"] {
        background-color: #1E2130;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        border: 1px solid #2b2e40;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 15px rgba(0, 0, 0, 0.3);
        border-color: #4A90E2;
    }
    button[data-testid="baseButton-primary"] {
        background: linear-gradient(90deg, #4A90E2 0%, #00C9FF 100%);
        border: none;
    }
    .main-title {
        font-size: 42px;
        font-weight: 800;
        background: -webkit-linear-gradient(45deg, #4A90E2, #00C9FF);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
    }
    .sub-title {
        color: #A0AEC0;
        font-size: 16px;
        margin-bottom: 30px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# ☁️ SUPABASE CLOUD DATABASE SYSTEM
# ==========================================
SUPABASE_URL = "https://ayedgiyciuwyousmfhvr.supabase.co"
SUPABASE_KEY = "sb_publishable_SsA9pIMsjpC-uF6Zsh31Jw_-MSZKEDF"

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_connection()

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
NEW_CARS_DB_FILE = os.path.join(CURRENT_DIR, "new_car_prices.csv")

def load_new_car_prices():
    if os.path.exists(NEW_CARS_DB_FILE): return pd.read_csv(NEW_CARS_DB_FILE)
    return pd.DataFrame()

def load_cloud_db():
    try:
        response = supabase.table('dealership_database').select('*').execute()
        if response.data:
            return pd.DataFrame(response.data)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"🚨 Cloud DB Error: {e}")
        return pd.DataFrame()

def save_to_cloud_db(new_data_list):
    if not new_data_list: return
    
    # 1. Clean internal duplicates from the scrape batch
    unique_scraped_data = list({item['Listing_URL']: item for item in new_data_list}.values())
    
    success_count = 0
    # 2. Insert one by one. If it's a duplicate, simply ignore it!
    for car in unique_scraped_data:
        try:
            supabase.table('dealership_database').insert(car).execute()
            success_count += 1
        except Exception as e:
            # If the error is about a duplicate key, silently bypass it
            if "duplicate key" in str(e).lower() or "23505" in str(e):
                continue
            else:
                pass 
                
    if success_count > 0:
        st.toast(f"☁️ Successfully added {success_count} NEW cars to Supabase!")
    else:
        st.toast("ℹ️ Scan finished. All found cars are already in your database.")

def format_inr(number):
    try:
        is_negative = number < 0
        number = abs(int(number))
        s, *d = str(number).partition(".")
        r = ",".join([s[x-2:x] for x in range(-3, -len(s), -2)][::-1] + [s[-3:]]) if len(s) > 3 else s
        res = f"₹{r}"
        return f"-{res}" if is_negative else res
    except: return f"₹{number}"

if 'scraped_data' not in st.session_state: st.session_state.scraped_data = []
if 'scan_complete' not in st.session_state: st.session_state.scan_complete = False

current_year = datetime.now().year
today_date = datetime.now().strftime("%Y-%m-%d")
new_cars_df = load_new_car_prices()

INDIAN_STATES = {
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Thane", "Nashik", "Navi Mumbai"],
    "Delhi NCR": ["Delhi", "New Delhi", "Noida", "Gurgaon", "Gurugram", "Faridabad", "Ghaziabad"],
    "Karnataka": ["Bangalore", "Bengaluru", "Mysore"],
    "Telangana": ["Hyderabad", "Secunderabad"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai"],
    "West Bengal": ["Kolkata", "Howrah"],
    "Uttar Pradesh": ["Lucknow", "Kanpur", "Agra", "Varanasi"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur"],
    "Madhya Pradesh": ["Indore", "Bhopal"],
    "Punjab": ["Ludhiana", "Amritsar", "Chandigarh"],
    "Kerala": ["Kochi", "Trivandrum"]
}

def extract_city_state(text, requested_location, url=""):
    url_lower = str(url).lower()
    if requested_location and requested_location.strip().lower() not in ["", "india", "pan india", "pan-india"]:
        req_loc = requested_location.title()
        for state, cities in INDIAN_STATES.items():
            if req_loc in cities or req_loc.lower() == state.lower(): return req_loc, state
        return req_loc, "Unknown"
    for state, cities in INDIAN_STATES.items():
        for city in cities:
            if city.lower() in url_lower: return city, state
    text_lower = str(text).lower()
    for state, cities in INDIAN_STATES.items():
        for city in cities:
            if city.lower() in text_lower: return city, state
    return "Pan-India", "National"

def calculate_idv(historical_ex_showroom_price, age):
    if age <= 0: depreciation = 0.05
    elif age == 1: depreciation = 0.15
    elif age == 2: depreciation = 0.20
    elif age == 3: depreciation = 0.30
    elif age == 4: depreciation = 0.40
    elif age == 5: depreciation = 0.50
    else: depreciation = min(0.50 + (age - 5) * 0.10, 0.85) 
    return int(historical_ex_showroom_price * (1 - depreciation))

def extract_advanced_details(text, input_rto):
    text_lower = text.lower()
    owner = "1st"
    if re.search(r'(2nd|second)', text_lower): owner = "2nd"
    elif re.search(r'(3rd|third)', text_lower): owner = "3rd"
    elif re.search(r'(4th|fourth)', text_lower): owner = "4th"
    
    rto = input_rto.upper() if input_rto else "N/A"
    if not input_rto:
        rto_match = re.search(r'([A-Z]{2}[-\s]?[0-9]{1,2})', text.upper())
        if rto_match: rto = rto_match.group(1)
            
    colors = ['white', 'black', 'silver', 'grey', 'gray', 'red', 'blue', 'brown']
    color = next((c.title() for c in colors if c in text_lower), "N/A")
    dealer = "Dealer" if any(w in text_lower for w in ["dealer", "featured", "warranty"]) else "Individual/Unverified"
    
    listing_date = "Hidden by Dealer"
    date_match = re.search(r'(\d+\s+(?:day|days|hour|hours|week|weeks|month|months)\s+ago)', text_lower)
    month_match = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}', text_lower)
    if date_match: listing_date = date_match.group(1).title()
    elif month_match: listing_date = month_match.group(0).title()
    
    return owner, rto, color, dealer, listing_date

def get_olx_data(brand, model, location, input_rto):
    scraped_data = []
    driver = Driver(uc=True, headless=True)
    try:
        url = f"https://www.olx.in/{location.lower().replace(' ', '-')}_g4058877/cars_c84/q-{brand}-{model}" if location and location.strip().lower() not in ["", "india", "pan india", "pan-india"] else f"https://www.olx.in/cars_c84/q-{brand}-{model}"
        driver.get(url)
        time.sleep(3) 
        for _ in range(4): 
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)
            try: driver.execute_script("arguments[0].click();", driver.find_element(By.XPATH, "//button[@data-aut-id='btnLoadMore' or contains(translate(text(), 'LOAD MORE', 'load more'), 'load more')]")); time.sleep(1.5) 
            except: pass
        cards = driver.find_elements(By.XPATH, "//li[contains(@data-aut-id, 'itemBox')]") or driver.find_elements(By.TAG_NAME, "li")
        for card in cards:
            text = card.text.strip()
            if "₹" in text and model.lower().replace("-", " ") in text.lower().replace("-", " "):
                try:
                    price_match = re.search(r'₹\s*([\d,]+)', text)
                    if price_match:
                        price_num = int(price_match.group(1).replace(",", ""))
                        if price_num < 50000: continue
                        year_match = re.search(r'(201[0-9]|202[0-9])', text)
                        km_match = re.search(r'([\d,]+)\s*km', text.lower())
                        if not year_match or not km_match: continue
                        listing_url = card.find_element(By.TAG_NAME, "a").get_attribute("href")
                        owner, rto, color, dealer, list_date = extract_advanced_details(text, input_rto)
                        variant = next((line for line in text.split('\n') if model.lower() in line.lower() and len(line) > len(model)), "Standard")
                        actual_city, actual_state = extract_city_state(text, location, listing_url)
                        scraped_data.append({"Make/Brand": brand, "Model": model, "Variant": variant, "Reg_Year": int(year_match.group(1)), "Age": (current_year - int(year_match.group(1))), "Owner": owner, "Transmission": "Automatic" if "auto" in text.lower() or "at" in text.lower() else "Manual", "Fuel_Type": "Diesel" if "diesel" in text.lower() else ("CNG" if "cng" in text.lower() else "Petrol"), "Dealer_Name": dealer, "Kilometer": int(km_match.group(1).replace(",", "")), "RTO": rto, "Color": color, "Price_Raw": price_num, "Price_Lakhs": round(price_num / 100000, 2), "Location": actual_city, "State": actual_state, "Listing_Date": list_date, "Date_Found": today_date, "Listing_URL": listing_url, "Source": "OLX"})
                except: continue 
    finally:
        try: driver.quit()
        except: pass
    return scraped_data

def get_carwale_data(brand, model, location, input_rto):
    scraped_data = []
    driver = Driver(uc=True, headless=True) 
    try:
        b_fmt, m_fmt = brand.lower().replace(" ", "-"), model.lower().replace(" ", "-")
        url = f"https://www.carwale.com/used/{b_fmt}-{m_fmt}-cars-in-{location.lower().replace(' ', '-')}/" if location and location.strip().lower() not in ["", "india", "pan india", "pan-india"] else f"https://www.carwale.com/used/{b_fmt}-{m_fmt}-cars/"
        driver.get(url)
        time.sleep(5)
        try: driver.execute_script("var junk = document.querySelectorAll('iframe, [role=\"dialog\"], .modal, [class*=\"ad-\"], [id*=\"ad-\"], [class*=\"overlay\"]'); junk.forEach(j => j.remove()); document.body.style.overflow = 'auto';")
        except: pass
        for _ in range(6): driver.execute_script("window.scrollBy(0, 800);"); time.sleep(1.5)
        cards = driver.find_elements(By.TAG_NAME, "a")
        for card in cards:
            try:
                text = card.get_attribute("textContent") or card.text
                if not text: continue
                text = text.replace('\n', ' ').strip()
                if model.lower().replace("-", " ") not in text.lower(): continue 
                listing_url = card.get_attribute("href")
                if not listing_url or len(listing_url) < 15: continue
                price_num = 0
                if re.search(r'(\d+\.?\d*)\s*(?:Lakh|Lac)', text, re.IGNORECASE): price_num = int(float(re.search(r'(\d+\.?\d*)\s*(?:Lakh|Lac)', text, re.IGNORECASE).group(1)) * 100000)
                elif re.search(r'(?:₹|Rs\.?)\s*([\d,]+)', text): price_num = int(re.search(r'(?:₹|Rs\.?)\s*([\d,]+)', text).group(1).replace(",", ""))
                if price_num < 50000: continue
                year_match = re.search(r'(201[0-9]|202[0-9])', text)
                km_match = re.search(r'([\d,]+)\s*(?:km|kms)', text.lower())
                if not year_match or not km_match: continue
                owner, rto, color, dealer, list_date = extract_advanced_details(text, input_rto)
                variant = next((line for line in text.split(' ') if len(line) > 3 and line.lower() not in brand.lower() and line.lower() not in model.lower()), "Standard")
                actual_city, actual_state = extract_city_state(text, location, listing_url)
                scraped_data.append({"Make/Brand": brand, "Model": model, "Variant": text[:35] + "...", "Reg_Year": int(year_match.group(1)), "Age": (current_year - int(year_match.group(1))), "Owner": owner, "Transmission": "Automatic" if "auto" in text.lower() or "at" in text.lower() else "Manual", "Fuel_Type": "Diesel" if "diesel" in text.lower() else ("CNG" if "cng" in text.lower() else "Petrol"), "Dealer_Name": "CarWale Verified", "Kilometer": int(km_match.group(1).replace(",", "")), "RTO": rto, "Color": color, "Price_Raw": price_num, "Price_Lakhs": round(price_num / 100000, 2), "Location": actual_city, "State": actual_state, "Listing_Date": list_date, "Date_Found": today_date, "Listing_URL": listing_url, "Source": "CarWale"})
            except: continue 
    finally:
        try: driver.quit()
        except: pass
    return scraped_data

def get_cars24_data(brand, model, location, input_rto):
    scraped_data = []
    driver = Driver(uc=True, headless=True) 
    try:
        b_fmt = brand.lower().replace(" ", "-")
        m_fmt = model.lower().replace(" ", "-")
        is_pan_india = not location or location.strip().lower() in ["", "india", "pan india", "pan-india"]
        safe_loc = "new-delhi" if is_pan_india else location.lower().replace(' ', '-')
        url = f"https://www.cars24.com/buy-used-{b_fmt}-{m_fmt}-cars-{safe_loc}/"
        driver.get(url)
        time.sleep(6) 
        try: driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE); time.sleep(1)
        except: pass
        try:
            target_city = "New Delhi" if is_pan_india else location.title()
            city_btns = driver.find_elements(By.XPATH, f"//*[contains(text(), '{target_city}')]")
            if city_btns: driver.execute_script("arguments[0].click();", city_btns[0]); time.sleep(3)
        except: pass
        try: driver.execute_script("var junk = document.querySelectorAll('iframe, [role=\"dialog\"], .modal, [class*=\"overlay\"], [class*=\"bottom-sheet\"]'); junk.forEach(j => j.remove()); document.body.style.overflow = 'auto';")
        except: pass
        for _ in range(6): driver.execute_script("window.scrollBy(0, 800);"); time.sleep(1.5)
        cards = driver.find_elements(By.TAG_NAME, "a")
        for card in cards:
            try:
                text = card.get_attribute("textContent") or card.text
                if not text: continue
                text = text.replace('\n', ' ').strip()
                if model.lower().replace("-", " ") not in text.lower(): continue 
                listing_url = card.get_attribute("href")
                if not listing_url or "/buy-used-" not in listing_url: continue 
                price_num = 0
                if re.search(r'₹\s*([\d,]+)', text): price_num = int(re.search(r'₹\s*([\d,]+)', text).group(1).replace(",", ""))
                elif re.search(r'(\d+\.?\d*)\s*(?:Lakh|Lac)', text, re.IGNORECASE): price_num = int(float(re.search(r'(\d+\.?\d*)\s*(?:Lakh|Lac)', text, re.IGNORECASE).group(1)) * 100000)
                if price_num < 50000: continue
                year_match = re.search(r'(201[0-9]|202[0-9])', text)
                km_match = re.search(r'([\d,]+)\s*(?:km|kms)', text.lower())
                if not year_match or not km_match: continue
                owner, rto, color, dealer, list_date = extract_advanced_details(text, input_rto)
                actual_city, actual_state = extract_city_state(text, location, listing_url)
                scraped_data.append({"Make/Brand": brand, "Model": model, "Variant": text[:35] + "...", "Reg_Year": int(year_match.group(1)), "Age": (current_year - int(year_match.group(1))), "Owner": owner, "Transmission": "Automatic" if "auto" in text.lower() or "at" in text.lower() else "Manual", "Fuel_Type": "Diesel" if "diesel" in text.lower() else ("CNG" if "cng" in text.lower() else "Petrol"), "Dealer_Name": "Cars24 Verified", "Kilometer": int(km_match.group(1).replace(",", "")), "RTO": rto, "Color": color, "Price_Raw": price_num, "Price_Lakhs": round(price_num / 100000, 2), "Location": actual_city, "State": actual_state, "Listing_Date": list_date, "Date_Found": today_date, "Listing_URL": listing_url, "Source": "Cars24"})
            except: continue 
    finally:
        try: driver.quit()
        except: pass
    return scraped_data

with st.sidebar:
    st.markdown("<h2 style='text-align: center; color: #4A90E2;'>☁️ DealerIntel Cloud</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray; font-size: 12px; margin-top:-15px;'>Supabase Connected API</p>", unsafe_allow_html=True)
    st.divider()
    
    INDIAN_CARS_DB = {
        "Maruti Suzuki": ["Swift", "Baleno", "Wagon R", "Brezza", "Ertiga", "Dzire", "Alto", "Alto K10", "Fronx", "Grand Vitara", "Jimny", "Celerio", "Ignis", "Ciaz", "XL6"],
        "Hyundai": ["Creta", "Venue", "i20", "Grand i10", "Verna", "Exter", "Aura", "Alcazar", "Santro", "Tucson"],
        "Tata": ["Nexon", "Punch", "Harrier", "Safari", "Tiago", "Altroz", "Tigor", "Curvv"],
        "Mahindra": ["Scorpio", "Scorpio-N", "XUV700", "Thar", "XUV500", "XUV300", "XUV3X0", "Bolero"],
        "Kia": ["Seltos", "Sonet", "Carens", "Carnival"],
        "Toyota": ["Innova", "Innova Crysta", "Innova Hycross", "Fortuner", "Glanza", "Urban Cruiser", "Hyryder"],
        "Honda": ["City", "Amaze", "Elevate"],
        "MG": ["Hector", "Astor", "Gloster", "Comet EV", "ZS EV"],
        "Skoda": ["Kushaq", "Slavia", "Kodiaq", "Kylaq"],
        "Volkswagen": ["Polo", "Vento", "Taigun", "Virtus", "Tiguan"],
        "Porsche": ["Macan", "Cayenne", "911"],
        "BMW": ["3 Series", "5 Series", "X1", "X5"],
        "Mercedes-Benz": ["C-Class", "E-Class", "GLA", "GLC"]
    }
    
    brand = st.selectbox("Make/Brand", list(INDIAN_CARS_DB.keys()), index=0)
    model = st.selectbox("Model", INDIAN_CARS_DB[brand])
    
    available_variants = ["Any / Not Sure"]
    if not new_cars_df.empty:
        model_variants = new_cars_df[(new_cars_df['Make'] == brand) & (new_cars_df['Model'] == model)]['Variant'].tolist()
        if model_variants: available_variants.extend(model_variants)
    
    selected_new_variant = st.selectbox("Benchmark Variant (For New Price)", available_variants)
    variant_input = st.text_input("Strict Variant Filter (e.g., 'SX')")
    year_toggle = st.checkbox("Exact Year Match", value=False)
    reg_year_input = st.number_input("Reg. Year", min_value=2000, max_value=current_year, value=2019, step=1, disabled=not year_toggle)
    km_driven = st.number_input("Kilometers Driven (Target Car)", value=None, placeholder="e.g., 45000", step=1000)
    
    st.subheader("Filter Specs")
    state_input = st.selectbox("Target State", ["All India"] + list(INDIAN_STATES.keys()))
    owner_input = st.selectbox("Ownership", ["Any", "1st Owner", "2nd Owner", "3rd+ Owner"])
    fuel_input = st.selectbox("Strict Fuel Type", ["Any", "Petrol", "Diesel", "CNG", "Electric"])
    transmission_input = st.selectbox("Transmission", ["Any", "Manual", "Automatic"])
    
    st.subheader("Deal Economics")
    target_margin = st.slider("Target Margin (%)", min_value=1, max_value=30, value=12)
    negotiation_buffer = st.slider("Negotiation Buffer (%)", min_value=0, max_value=20, value=7)
    customer_asking_price = st.number_input("Customer Asking Price (₹)", value=None, placeholder="e.g., 500000", step=10000)
    
    st.divider()
    selected_platforms = st.multiselect("Data Sources", ["OLX", "CarWale", "Cars24"], default=["OLX", "CarWale", "Cars24"])
    live_scan = st.toggle("⚡ Deep Web Scan (API)", value=False)
    run_button = st.button(f"Analyze Deal Valuation", type="primary", use_container_width=True)

st.markdown('<p class="main-title">DealerIntel AI</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Real-Time Automotive Market Intelligence & Bidding Strategy</p>', unsafe_allow_html=True)

scraper_functions = {"OLX": get_olx_data, "CarWale": get_carwale_data, "Cars24": get_cars24_data}

if run_button:
    new_raw_data = []
    if live_scan:
        st.info("📡 Connecting to Market APIs via Throttled Proxy Nodes...")
        my_bar = st.progress(0)
        for index, plat in enumerate(selected_platforms):
            my_bar.progress((index) / len(selected_platforms), text=f"Scraping {plat} Engine...")
            try:
                loc_to_search = INDIAN_STATES[state_input][0] if state_input != "All India" else ""
                data = scraper_functions[plat](brand, model, loc_to_search, None)
                new_raw_data.extend(data)
                if not data: st.toast(f"ℹ️ {plat}: No inventory found.")
            except Exception: st.error(f"Timeout on {plat}. Anti-bot defense triggered.")
        my_bar.progress(1.0, text="✅ Aggregation Complete. Pushing to Supabase Cloud...")
        save_to_cloud_db(new_raw_data)
    else:
        st.info("⚡ Instant Search: Querying Supabase Cloud Database...")

    master_db = load_cloud_db()
    
    if master_db.empty: st.error("Database is empty. Turn on Deep Web Scan to collect data.")
    else:
        filtered_db = master_db.copy()
        filtered_db = filtered_db[(filtered_db['Reg_Year'] >= 2000) & (filtered_db['Kilometer'] > 0)]
        filtered_db = filtered_db[filtered_db['Source'].isin(selected_platforms)]
        filtered_db = filtered_db[(filtered_db['Make/Brand'] == brand) & (filtered_db['Model'] == model)]
        
        if state_input != "All India": filtered_db = filtered_db[filtered_db['State'] == state_input]
        if fuel_input != "Any": filtered_db = filtered_db[filtered_db['Fuel_Type'] == fuel_input]
        if transmission_input != "Any": filtered_db = filtered_db[filtered_db['Transmission'] == transmission_input]
        if owner_input != "Any": filtered_db = filtered_db[filtered_db['Owner'] == ("1st" if owner_input == "1st Owner" else "2nd" if owner_input == "2nd Owner" else "3rd")]
        if variant_input.strip(): filtered_db = filtered_db[filtered_db['Variant'].str.contains(variant_input, case=False, na=False)]

        st.session_state.scraped_data = filtered_db.to_dict('records')
        st.session_state.scan_complete = True

if st.session_state.scan_complete:
    if len(st.session_state.scraped_data) > 0:
        df_calc = pd.DataFrame(st.session_state.scraped_data).drop_duplicates(subset=['Price_Raw', 'Kilometer', 'Location', 'Reg_Year'])
        
        if year_toggle:
            df_calc_year = df_calc[df_calc["Reg_Year"] == reg_year_input]
            if df_calc_year.empty: st.warning(f"⚠️ No matches for {reg_year_input}. Showing broader market trends.")
            else: df_calc = df_calc_year

        clean_market = df_calc[(df_calc["Price_Raw"] >= df_calc["Price_Raw"].quantile(0.15)) & (df_calc["Price_Raw"] <= df_calc["Price_Raw"].quantile(0.85))]
        if clean_market.empty: clean_market = df_calc
        
        base_retail_price = int(clean_market["Price_Raw"].median())
        market_avg_km = clean_market["Kilometer"].median()
        
        safe_km = km_driven if km_driven is not None else market_avg_km
        true_retail_value = int(base_retail_price - ((safe_km - market_avg_km) / 10000) * (base_retail_price * 0.02))
        
        safe_retail_value_for_math = true_retail_value if true_retail_value > 0 else 1
        
        target_profit_amount = int(true_retail_value * (target_margin / 100))
        max_buying_price = true_retail_value - target_profit_amount
        starting_offer_price = max_buying_price - int(max_buying_price * (negotiation_buffer / 100))

        tab1, tab2 = st.tabs(["📊 Valuation Desk", "📈 Market Analytics & Download"])

        with tab1:
            st.markdown(f"### 📊 Step 1: Market Intelligence | Based on {len(clean_market)} Matches")
            new_car_price, historical_ex_showroom, idv_value = None, None, "N/A"
            if selected_new_variant != "Any / Not Sure" and not new_cars_df.empty:
                match = new_cars_df[(new_cars_df['Make'] == brand) & (new_cars_df['Model'] == model) & (new_cars_df['Variant'] == selected_new_variant)]
                if not match.empty:
                    new_car_price = int(match.iloc[0]['Ex_Showroom_Price'])
                    calc_age = current_year - reg_year_input if year_toggle else current_year - int(df_calc['Reg_Year'].median())
                    historical_ex_showroom = int(new_car_price / ((1 + 0.045) ** calc_age)) if calc_age > 0 else new_car_price
                    idv_value = calculate_idv(historical_ex_showroom, calc_age)

            c1, c2, c3 = st.columns(3)
            c1.metric("Expected Retail Market Price", format_inr(true_retail_value))
            c2.metric("IRDAI Book Value (IDV)", format_inr(idv_value) if idv_value != "N/A" else "Select Variant")
            c3.metric("Est. Original Price (When New)", format_inr(historical_ex_showroom) if historical_ex_showroom else "Select Variant")

            st.divider()
            st.markdown("### 🎯 Step 2: Bidding Strategy (What to pay)")
            c1, c2, c3 = st.columns(3)
            c1.metric("Recommended Starting Offer", format_inr(starting_offer_price))
            c2.metric("Absolute Max Buy Price", format_inr(max_buying_price))
            
            if customer_asking_price:
                actual_profit = true_retail_value - customer_asking_price
                actual_margin = (actual_profit / safe_retail_value_for_math) * 100 if true_retail_value > 0 else 0
                c3.metric("Projected Profit (at Asking Price)", format_inr(actual_profit), f"{actual_margin:.1f}% Margin", delta_color="normal")
            else:
                c3.metric("Target Deal Profit", format_inr(target_profit_amount), f"Assuming {target_margin}% Margin")

            if customer_asking_price is not None:
                st.divider()
                st.subheader("📋 Procurement Decision (P&L)")
                projected_net_profit = true_retail_value - customer_asking_price
                actual_margin_pct = (projected_net_profit / safe_retail_value_for_math) * 100 if true_retail_value > 0 else 0
                
                box_color = "#0e2a14" if customer_asking_price <= max_buying_price else "#2a0e0e"
                icon = "✅" if customer_asking_price <= max_buying_price else "🚨"
                status = "DEAL APPROVED (Asking Price is Safe)" if customer_asking_price <= max_buying_price else "DO NOT BUY (Asking Price exceeds Max Buy)"

                st.markdown(f"""
                <div style="background-color: {box_color}; padding: 20px; border-radius: 10px; border: 1px solid #444;">
                    <h4 style="margin-top:0px;">{icon} Deal Status: {status}</h4>
                    <p style="margin: 5px 0; color: #A0AEC0;"><strong>Expected Retail Revenue:</strong> {format_inr(true_retail_value)}</p>
                    <p style="margin: 5px 0; color: #A0AEC0;"><strong>(-) Customer Asking Price:</strong> {format_inr(customer_asking_price)}</p>
                    <hr style="border-color: #555; margin: 10px 0;">
                    <h3 style="margin-bottom:0px;">Actual Net Profit / (Loss): {format_inr(projected_net_profit)} <span style="font-size: 16px; font-weight: normal; color: gray;"> ({actual_margin_pct:.1f}% Margin)</span></h3>
                </div>
                """, unsafe_allow_html=True)

        with tab2:
            st.markdown("#### Market Isolation Plot")
            fig = px.scatter(df_calc, x="Kilometer", y="Price_Lakhs", color="State", hover_data=["Variant", "Reg_Year", "Dealer_Name", "Source"], template="plotly_dark")
            fig.add_scatter(x=[safe_km], y=[round(max_buying_price/100000, 2)], mode="markers+text", marker=dict(color="#00FF00", size=20, symbol="star"), name="MAX BUY PRICE", text=["★ MAX BUY"], textposition="top center")
            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df_calc, use_container_width=True, hide_index=True)
    else: st.error("🚨 No inventory match. Turn 'Deep Web Scan' ON to query live data.")