import streamlit as st
import pandas as pd
from selenium.webdriver.common.by import By
from seleniumbase import Driver
import time
import re
import os
import plotly.express as px
from datetime import datetime
import concurrent.futures

# ==========================================
# 🚀 1. UI & BRANDING CONFIGURATION
# ==========================================
st.set_page_config(page_title="DealerIntel AI | Procurement", page_icon="🌐", layout="wide", initial_sidebar_state="expanded")

# CUSTOM CSS FOR PROFESSIONAL SAAS UI & ANIMATIONS
st.markdown("""
<style>
    /* Card Hover Animations */
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
    /* Gradient Button */
    button[data-testid="baseButton-primary"] {
        background: linear-gradient(90deg, #4A90E2 0%, #00C9FF 100%);
        border: none;
        transition: transform 0.2s ease;
    }
    button[data-testid="baseButton-primary"]:hover {
        transform: scale(1.02);
    }
    /* Main Title Styling */
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
# 💾 THE LOCAL DATABASE SYSTEM
# ==========================================
DB_FILE = "dealership_database.csv"

def load_local_db():
    if os.path.exists(DB_FILE): return pd.read_csv(DB_FILE)
    return pd.DataFrame()

def save_to_db(new_data_list):
    if not new_data_list: return
    new_df = pd.DataFrame(new_data_list)
    if os.path.exists(DB_FILE):
        old_df = pd.read_csv(DB_FILE)
        combined = pd.concat([old_df, new_df]).drop_duplicates(subset=['Listing_URL'], keep='first')
        combined.to_csv(DB_FILE, index=False)
    else:
        new_df.to_csv(DB_FILE, index=False)

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

# ==========================================
# 🧩 HELPER FUNCTIONS & ADAPTERS
# ==========================================
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
        driver.get(f"https://www.olx.in/cars_c84/q-{brand}-{model}")
        time.sleep(3) 
        for _ in range(3): 
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            try:
                driver.execute_script("arguments[0].click();", driver.find_element(By.XPATH, "//button[@data-aut-id='btnLoadMore' or contains(translate(text(), 'LOAD MORE', 'load more'), 'load more')]"))
                time.sleep(1.5) 
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
                        year_match = re.search(r'(20\d{2})\s*-', text)
                        km_match = re.search(r'([\d,]+)\s*km', text.lower())
                        owner, rto, color, dealer, list_date = extract_advanced_details(text, input_rto)
                        variant = next((line for line in text.split('\n') if model.lower() in line.lower() and len(line) > len(model)), "N/A")
                        
                        scraped_data.append({
                            "Make/Brand": brand, "Model": model, "Variant": variant,
                            "Reg_Year": int(year_match.group(1)) if year_match else 0, "Age": (current_year - int(year_match.group(1))) if year_match else 0,
                            "Owner": owner, "Transmission": "Automatic" if "auto" in text.lower() or "at" in text.lower() else "Manual",
                            "Fuel_Type": "Diesel" if "diesel" in text.lower() else ("CNG" if "cng" in text.lower() else "Petrol"),
                            "Dealer_Name": dealer, "Kilometer": int(km_match.group(1).replace(",", "")) if km_match else 0,
                            "RTO": rto, "Color": color, "Price_Raw": price_num, "Price_Lakhs": round(price_num / 100000, 2),
                            "Location": location if location else "Pan-India", "Listing_Date": list_date, "Date_Found": today_date,
                            "Listing_URL": card.find_element(By.TAG_NAME, "a").get_attribute("href"), "Source": "OLX"
                        })
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
        driver.get(f"https://www.carwale.com/used/{b_fmt}-{m_fmt}-cars-in-{location.lower().replace(' ', '-')}/" if location else f"https://www.carwale.com/used/{b_fmt}-{m_fmt}-cars/")
        time.sleep(3)
        for _ in range(4):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
        cards = driver.find_elements(By.XPATH, "//h3/ancestor::div[position()=1 or position()=2 or position()=3]") or driver.find_elements(By.TAG_NAME, "div")
        for card in cards:
            text = card.text.strip()
            if ("₹" in text or "Lakh" in text.lower()) and model.lower().replace("-", " ") in text.lower().replace("-", " "):
                try:
                    price_num = 0
                    if re.search(r'(\d+\.?\d*)\s*Lakh', text, re.IGNORECASE): price_num = int(float(re.search(r'(\d+\.?\d*)\s*Lakh', text, re.IGNORECASE).group(1)) * 100000)
                    elif re.search(r'₹\s*([\d,]+)', text): price_num = int(re.search(r'₹\s*([\d,]+)', text).group(1).replace(",", ""))
                    if price_num < 50000: continue
                    
                    year_match = re.search(r'(20\d{2})', text)
                    km_match = re.search(r'([\d,]+)\s*km', text.lower())
                    owner, rto, color, dealer, list_date = extract_advanced_details(text, input_rto)
                    
                    scraped_data.append({
                        "Make/Brand": brand, "Model": model, "Variant": "N/A",
                        "Reg_Year": int(year_match.group(1)) if year_match else 0, "Age": (current_year - int(year_match.group(1))) if year_match else 0,
                        "Owner": owner, "Transmission": "Automatic" if "auto" in text.lower() or "at" in text.lower() else "Manual",
                        "Fuel_Type": "Diesel" if "diesel" in text.lower() else ("CNG" if "cng" in text.lower() else "Petrol"),
                        "Dealer_Name": dealer, "Kilometer": int(km_match.group(1).replace(",", "")) if km_match else 0,
                        "RTO": rto, "Color": color, "Price_Raw": price_num, "Price_Lakhs": round(price_num / 100000, 2),
                        "Location": location.title() if location else "Pan-India", "Listing_Date": list_date, "Date_Found": today_date,
                        "Listing_URL": card.find_element(By.TAG_NAME, "a").get_attribute("href"), "Source": "CarWale"
                    })
                except: continue 
    finally:
        try: driver.quit()
        except: pass
    return scraped_data

def get_spinny_data(brand, model, location, input_rto):
    scraped_data = []
    driver = Driver(uc=True, headless=True)
    try:
        b_fmt, m_fmt = brand.lower().replace(" ", "-"), model.lower().replace(" ", "-")
        driver.get(f"https://www.spinny.com/used-{b_fmt}-{m_fmt}-cars-in-{location.lower().replace(' ', '-')}/s/" if location else f"https://www.spinny.com/used-{b_fmt}-{m_fmt}-cars/s/")
        time.sleep(4) 
        for _ in range(4):
            driver.execute_script("window.scrollBy(0, 800);")
            time.sleep(1)
        for card in driver.find_elements(By.TAG_NAME, "a"):
            try:
                text = card.text.strip()
                if model.lower().replace("-", " ") not in text.lower().replace("-", " "): continue 
                listing_url = card.get_attribute("href")
                if not listing_url or ("used-" not in listing_url and "buy-used-cars" not in listing_url): continue 
                
                price_num = 0
                if re.search(r'(\d+\.?\d*)\s*Lakh', text, re.IGNORECASE): price_num = int(float(re.search(r'(\d+\.?\d*)\s*Lakh', text, re.IGNORECASE).group(1)) * 100000)
                elif re.search(r'(?:₹|Rs\.?)\s*([\d,]+)', text): price_num = int(re.search(r'(?:₹|Rs\.?)\s*([\d,]+)', text).group(1).replace(",", ""))
                if price_num < 50000: continue
                
                year_match = re.search(r'(20\d{2})', text)
                km_match = re.search(r'([\d,]+)\s*km', text.lower())
                owner, rto, color, dealer, list_date = extract_advanced_details(text, input_rto)
                
                scraped_data.append({
                    "Make/Brand": brand, "Model": model, "Variant": "N/A", 
                    "Reg_Year": int(year_match.group(1)) if year_match else 0, "Age": (current_year - int(year_match.group(1))) if year_match else 0,
                    "Owner": owner, "Transmission": "Automatic" if "auto" in text.lower() or "at" in text.lower() else "Manual",
                    "Fuel_Type": "Diesel" if "diesel" in text.lower() else ("CNG" if "cng" in text.lower() else "Petrol"),
                    "Dealer_Name": "Spinny Assured", "Kilometer": int(km_match.group(1).replace(",", "")) if km_match else 0,
                    "RTO": rto, "Color": color, "Price_Raw": price_num, "Price_Lakhs": round(price_num / 100000, 2),
                    "Location": location.title() if location else "Pan-India", "Listing_Date": list_date, "Date_Found": today_date,
                    "Listing_URL": listing_url, "Source": "Spinny"
                })
            except: continue 
    finally:
        try: driver.quit()
        except: pass
    return scraped_data

def get_bbt_data(brand, model, location, input_rto):
    scraped_data = []
    driver = Driver(uc=True, headless=True)
    try:
        driver.get("https://www.bigboytoyz.com/collection")
        time.sleep(6)
        for _ in range(5):
            driver.execute_script("window.scrollBy(0, 1500);")
            time.sleep(1.5)
        for card in driver.find_elements(By.TAG_NAME, "a"):
            try:
                text = card.text.strip()
                if not text: continue
                if model.lower().replace("-", " ") in text.lower().replace("-", " "):
                    listing_url = card.get_attribute("href")
                    if not listing_url or "bigboytoyz.com" not in listing_url: continue
                    price_num = 0
                    if re.search(r'(\d+\.?\d*)\s*Cr', text, re.IGNORECASE): price_num = int(float(re.search(r'(\d+\.?\d*)\s*Cr', text, re.IGNORECASE).group(1)) * 10000000)
                    elif re.search(r'(\d+\.?\d*)\s*Lakh', text, re.IGNORECASE): price_num = int(float(re.search(r'(\d+\.?\d*)\s*Lakh', text, re.IGNORECASE).group(1)) * 100000)
                    elif re.search(r'(?:₹|Rs\.?)\s*([\d,]+)', text): price_num = int(re.search(r'(?:₹|Rs\.?)\s*([\d,]+)', text).group(1).replace(",", ""))
                    if price_num < 100000: continue
                    year_match = re.search(r'(20\d{2})', text)
                    km_match = re.search(r'([\d,]+)\s*(?:km|kms)', text.lower())
                    owner, rto, color, dealer, list_date = extract_advanced_details(text, input_rto)
                    scraped_data.append({
                        "Make/Brand": brand, "Model": model, "Variant": "Luxury", 
                        "Reg_Year": int(year_match.group(1)) if year_match else 0, "Age": (current_year - int(year_match.group(1))) if year_match else 0, "Owner": owner,
                        "Transmission": "Automatic", "Fuel_Type": "Petrol" if "petrol" in text.lower() else "Diesel", 
                        "Dealer_Name": "Big Boy Toyz", "Kilometer": int(km_match.group(1).replace(",", "")) if km_match else 0, "RTO": rto, "Color": color,
                        "Price_Raw": price_num, "Price_Lakhs": round(price_num / 100000, 2), "Location": "Pan-India",
                        "Listing_Date": list_date, "Date_Found": today_date, "Listing_URL": listing_url, "Source": "Big Boy Toyz"
                    })
            except: continue
    finally:
        try: driver.quit()
        except: pass
    return scraped_data

def get_autobest_data(brand, model, location, input_rto):
    scraped_data = []
    driver = Driver(uc=True, headless=True)
    try:
        driver.get("https://autobest.co.in/pre-owned-cars")
        time.sleep(6)
        for _ in range(3):
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(1)
        for card in driver.find_elements(By.TAG_NAME, "a"):
            try:
                text = card.text.strip()
                if not text: continue
                if model.lower().replace("-", " ") in text.lower().replace("-", " "):
                    listing_url = card.get_attribute("href")
                    if not listing_url: continue
                    price_num = 0
                    if re.search(r'(\d+\.?\d*)\s*Lakh', text, re.IGNORECASE): price_num = int(float(re.search(r'(\d+\.?\d*)\s*Lakh', text, re.IGNORECASE).group(1)) * 100000)
                    elif re.search(r'(?:₹|Rs\.?)\s*([\d,]+)', text): price_num = int(re.search(r'(?:₹|Rs\.?)\s*([\d,]+)', text).group(1).replace(",", ""))
                    if price_num < 100000: continue
                    year_match = re.search(r'(20\d{2})', text)
                    km_match = re.search(r'([\d,]+)\s*(?:Kms|km)', text.lower())
                    owner, rto, color, dealer, list_date = extract_advanced_details(text, input_rto)
                    scraped_data.append({
                        "Make/Brand": brand, "Model": model, "Variant": "Luxury", 
                        "Reg_Year": int(year_match.group(1)) if year_match else 0, "Age": (current_year - int(year_match.group(1))) if year_match else 0, "Owner": owner,
                        "Transmission": "Automatic", "Fuel_Type": "Petrol" if "petrol" in text.lower() else "Diesel", 
                        "Dealer_Name": "AutoBest Emporio", "Kilometer": int(km_match.group(1).replace(",", "")) if km_match else 0, "RTO": rto, "Color": color,
                        "Price_Raw": price_num, "Price_Lakhs": round(price_num / 100000, 2), "Location": "Delhi NCR",
                        "Listing_Date": list_date, "Date_Found": today_date, "Listing_URL": listing_url, "Source": "AutoBest"
                    })
            except: continue
    finally:
        try: driver.quit()
        except: pass
    return scraped_data

def get_autohangar_data(brand, model, location, input_rto):
    scraped_data = []
    driver = Driver(uc=True, headless=True)
    try:
        driver.get("https://www.autohangaradvantage.com/buy-a-car")
        time.sleep(6)
        for _ in range(4):
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(1)
        for card in driver.find_elements(By.TAG_NAME, "a"):
            try:
                text = card.text.strip()
                if not text: continue
                if model.lower().replace("-", " ") in text.lower().replace("-", " "):
                    listing_url = card.get_attribute("href")
                    if not listing_url: continue
                    price_num = 0
                    if re.search(r'(?:INR|₹)\s*(\d+\.?\d*)\s*Lakh', text, re.IGNORECASE): price_num = int(float(re.search(r'(?:INR|₹)\s*(\d+\.?\d*)\s*Lakh', text, re.IGNORECASE).group(1)) * 100000)
                    elif re.search(r'(?:₹|Rs\.?)\s*([\d,]+)', text): price_num = int(re.search(r'(?:₹|Rs\.?)\s*([\d,]+)', text).group(1).replace(",", ""))
                    if price_num < 100000: continue
                    year_match = re.search(r'(20\d{2})', text)
                    km_match = re.search(r'([\d,]+)\s*(?:Kms|km)', text.lower())
                    owner, rto, color, dealer, list_date = extract_advanced_details(text, input_rto)
                    scraped_data.append({
                        "Make/Brand": brand, "Model": model, "Variant": "Luxury", 
                        "Reg_Year": int(year_match.group(1)) if year_match else 0, "Age": (current_year - int(year_match.group(1))) if year_match else 0, "Owner": owner,
                        "Transmission": "Automatic", "Fuel_Type": "Petrol" if "petrol" in text.lower() else "Diesel", 
                        "Dealer_Name": "Auto Hangar Advantage", "Kilometer": int(km_match.group(1).replace(",", "")) if km_match else 0, "RTO": rto, "Color": color,
                        "Price_Raw": price_num, "Price_Lakhs": round(price_num / 100000, 2), "Location": "Mumbai",
                        "Listing_Date": list_date, "Date_Found": today_date, "Listing_URL": listing_url, "Source": "Auto Hangar"
                    })
            except: continue
    finally:
        try: driver.quit()
        except: pass
    return scraped_data

def get_audi_approved_data(brand, model, location, input_rto):
    scraped_data = []
    if brand.lower() != "audi": return scraped_data
    driver = Driver(uc=True, headless=True)
    try:
        driver.get("https://www.audiapprovedplus.in/buy")
        time.sleep(6)
        for _ in range(3):
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(1)
        for card in driver.find_elements(By.TAG_NAME, "a"):
            try:
                text = card.text.strip()
                if not text: continue
                if model.lower().replace("-", " ") in text.lower().replace("-", " "):
                    listing_url = card.get_attribute("href")
                    if not listing_url: continue
                    price_num = 0
                    if re.search(r'(\d+\.?\d*)\s*Lakh', text, re.IGNORECASE): price_num = int(float(re.search(r'(\d+\.?\d*)\s*Lakh', text, re.IGNORECASE).group(1)) * 100000)
                    elif re.search(r'(?:₹|Rs\.?)\s*([\d,]+)', text): price_num = int(re.search(r'(?:₹|Rs\.?)\s*([\d,]+)', text).group(1).replace(",", ""))
                    if price_num < 100000: continue
                    year_match = re.search(r'(20\d{2})', text)
                    km_match = re.search(r'([\d,]+)\s*(?:km|kms)', text.lower())
                    owner, rto, color, dealer, list_date = extract_advanced_details(text, input_rto)
                    scraped_data.append({
                        "Make/Brand": brand, "Model": model, "Variant": "Luxury", 
                        "Reg_Year": int(year_match.group(1)) if year_match else 0, "Age": (current_year - int(year_match.group(1))) if year_match else 0, "Owner": owner,
                        "Transmission": "Automatic", "Fuel_Type": "Petrol" if "petrol" in text.lower() else "Diesel", 
                        "Dealer_Name": "Audi Approved Plus", "Kilometer": int(km_match.group(1).replace(",", "")) if km_match else 0, "RTO": rto, "Color": color,
                        "Price_Raw": price_num, "Price_Lakhs": round(price_num / 100000, 2), "Location": "Pan-India",
                        "Listing_Date": list_date, "Date_Found": today_date, "Listing_URL": listing_url, "Source": "Audi Approved Plus"
                    })
            except: continue
    finally:
        try: driver.quit()
        except: pass
    return scraped_data

# ==========================================
# 🖥️ UI & SIDEBAR (SAAS DESIGN)
# ==========================================
with st.sidebar:
    # Adding a sleek text logo format
    st.markdown("<h2 style='text-align: center; color: #4A90E2;'>🌐 DealerIntel</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray; font-size: 12px; margin-top:-15px;'>B2B Procurement Engine</p>", unsafe_allow_html=True)
    st.divider()
    
    INDIAN_CARS_DB = {
        "Maruti Suzuki": ["Swift", "Baleno", "Wagon R", "Brezza", "Ertiga", "Dzire", "Alto", "Alto K10", "Fronx", "Grand Vitara", "Jimny", "Celerio", "Ignis", "Ciaz", "XL6", "S-Cross", "Vitara Brezza", "Omni", "Eeco", "Zen"],
        "Hyundai": ["Creta", "Venue", "i20", "Grand i10", "Verna", "Exter", "Aura", "Alcazar", "Santro", "Eon", "Tucson", "Xcent", "Elantra", "Santa Fe"],
        "Tata": ["Nexon", "Punch", "Harrier", "Safari", "Tiago", "Altroz", "Tigor", "Hexa", "Indica", "Nano", "Aria", "Sumo", "Zest", "Bolt", "Curvv"],
        "Renault": ["Kwid", "Triber", "Kiger", "Duster", "Captur", "Lodgy", "Pulse"],
        "Mahindra": ["Scorpio", "Scorpio-N", "XUV700", "Thar", "XUV500", "XUV300", "XUV3X0", "Bolero", "TUV300", "Marazzo", "KUV100", "Quanto", "Xylo"],
        "Kia": ["Seltos", "Sonet", "Carens", "Carnival", "EV6"],
        "Toyota": ["Innova", "Innova Crysta", "Innova Hycross", "Fortuner", "Glanza", "Urban Cruiser", "Hyryder", "Etios", "Corolla Altis", "Camry", "Yaris", "Vellfire"],
        "Honda": ["City", "Amaze", "Elevate", "Jazz", "WR-V", "Civic", "Brio", "CR-V", "BR-V", "Mobilio", "Accord"],
        "MG": ["Hector", "Hector Plus", "Astor", "Gloster", "Comet EV", "ZS EV", "Windsor EV"],
        "Skoda": ["Kushaq", "Slavia", "Rapid", "Octavia", "Superb", "Kodiaq", "Laura", "Fabia", "Yeti"],
        "Volkswagen": ["Polo", "Vento", "Taigun", "Virtus", "Ameo", "Jetta", "Tiguan", "Passat", "CrossPolo"],
        "Nissan": ["Magnite", "Micra", "Sunny", "Terrano", "Kicks", "X-Trail"],
        "Jeep": ["Compass", "Meridian", "Wrangler", "Grand Cherokee"],
        "Ford": ["EcoSport", "Endeavour", "Figo", "Aspire", "Freestyle", "Fiesta", "Mustang"],
        "Mercedes-Benz": ["C-Class", "E-Class", "S-Class", "GLA", "GLC", "GLE", "GLS", "A-Class", "CLA", "G-Class", "Maybach", "EQE", "EQS"],
        "BMW": ["3 Series", "5 Series", "7 Series", "X1", "X3", "X5", "X7", "Z4", "M2", "M3", "M4", "i4", "iX"],
        "Audi": ["A3", "A4", "A6", "A8", "Q3", "Q5", "Q7", "Q8", "e-tron", "TT", "R8"],
        "Volvo": ["XC40", "XC60", "XC90", "S60", "S90", "V40"],
        "Land Rover": ["Range Rover", "Range Rover Sport", "Range Rover Evoque", "Range Rover Velar", "Discovery", "Discovery Sport", "Defender"],
        "Jaguar": ["XE", "XF", "XJ", "F-Pace", "F-Type"],
        "Porsche": ["Macan", "Cayenne", "Panamera", "911", "Taycan", "718"],
        "Lexus": ["NX", "RX", "LX", "ES", "LS", "LM"],
        "Lamborghini": ["Urus", "Huracan", "Aventador", "Revuelto"],
        "Ferrari": ["Roma", "Portofino", "F8 Tributo", "SF90 Stradale", "296 GTB", "Purosangue"],
        "Rolls-Royce": ["Phantom", "Ghost", "Wraith", "Cullinan", "Dawn"],
        "Bentley": ["Continental GT", "Flying Spur", "Bentayga"]
    }
    
    st.subheader("Vehicle Profile")
    brand = st.selectbox("Make/Brand", list(INDIAN_CARS_DB.keys()), index=1)
    model = st.selectbox("Model", INDIAN_CARS_DB[brand])
    variant_input = st.text_input("Variant (Optional, e.g., 'SX')")
    
    year_toggle = st.checkbox("Exact Year Match", value=False)
    reg_year_input = st.number_input("Reg. Year", min_value=2000, max_value=current_year, value=2019, step=1, disabled=not year_toggle)
    
    st.subheader("Filter Specs")
    owner_input = st.selectbox("Ownership", ["Any", "1st Owner", "2nd Owner", "3rd+ Owner"])
    transmission_input = st.selectbox("Transmission", ["Any", "Manual", "Automatic"])
    fuel_input = st.selectbox("Fuel Type", ["Petrol", "Diesel", "CNG", "Electric", "Any"])
    
    st.subheader("Deal Economics")
    location = st.text_input("City/Location", value="", placeholder="Leave blank for Pan-India")
    customer_asking_price = st.number_input("Customer Asking Price (₹)", value=4000000, step=10000)
    target_margin = st.slider("Target Margin (%)", min_value=1, max_value=30, value=12)
    refurb_cost = st.number_input("Est. Refurbishment (₹)", value=None, placeholder="e.g., 15000", step=5000)
    safe_refurb_cost = refurb_cost if refurb_cost is not None else 0
    
    st.divider()
    platform_map = {
        "OLX (Stealth)": "OLX", "CarWale": "CarWale", "Spinny": "Spinny", 
        "Big Boy Toyz (Exotics)": "Big Boy Toyz", "AutoBest (Pre-Owned)": "AutoBest", 
        "Auto Hangar Advantage": "Auto Hangar", "Audi Approved Plus": "Audi Approved Plus"
    }
    selected_platforms = st.multiselect("Data Sources", list(platform_map.keys()), default=["OLX (Stealth)", "CarWale"])
    live_scan = st.toggle("⚡ Deep Web Scan (API)", value=False, help="Connects to live marketplaces. Turn off to query cached DB.")
    
    run_button = st.button(f"Analyze Deal Valuation", type="primary", use_container_width=True)

# ==========================================
# 🧠 MAIN DASHBOARD ENGINE
# ==========================================
st.markdown('<p class="main-title">DealerIntel AI</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Real-Time Automotive Market Intelligence & Bidding Strategy</p>', unsafe_allow_html=True)

scraper_functions = {
    "OLX (Stealth)": get_olx_data, "CarWale": get_carwale_data, "Spinny": get_spinny_data,
    "Big Boy Toyz (Exotics)": get_bbt_data, "AutoBest (Pre-Owned)": get_autobest_data,
    "Auto Hangar Advantage": get_autohangar_data, "Audi Approved Plus": get_audi_approved_data
}

if run_button:
    new_raw_data = []
    
    if live_scan:
        st.info("📡 Connecting to Market APIs via Throttled Proxy Nodes...")
        my_bar = st.progress(0, text="Initializing...")
        
        total_plats = len(selected_platforms)
        for index, plat in enumerate(selected_platforms):
            my_bar.progress((index) / total_plats, text=f"Scraping {plat} Engine...")
            try:
                data = scraper_functions[plat](brand, model, location, None)
                new_raw_data.extend(data)
                if not data: st.toast(f"ℹ️ {plat}: No inventory found.")
            except Exception: st.error(f"Timeout on {plat}. Anti-bot defense triggered.")
        
        my_bar.progress(1.0, text="✅ Aggregation Complete.")
        save_to_db(new_raw_data)
    else:
        st.info("⚡ Instant Search: Querying Cloud-Cached Memory...")

    master_db = load_local_db()
    
    if master_db.empty:
        st.error("Database is empty. Please enable 'Deep Web Scan' to ingest your first dataset.")
    else:
        filtered_db = master_db.copy()
        selected_source_names = [platform_map[p] for p in selected_platforms]
        filtered_db = filtered_db[filtered_db['Source'].isin(selected_source_names)]
        filtered_db = filtered_db[(filtered_db['Make/Brand'] == brand) & (filtered_db['Model'] == model)]
        if location: filtered_db = filtered_db[filtered_db['Location'].str.contains(location, case=False, na=False)]
        if year_toggle: filtered_db = filtered_db[filtered_db['Reg_Year'] == reg_year_input]
        if fuel_input != "Any": filtered_db = filtered_db[filtered_db['Fuel_Type'] == fuel_input]
        if transmission_input != "Any": filtered_db = filtered_db[filtered_db['Transmission'] == transmission_input]
        if owner_input != "Any":
            if owner_input == "1st Owner": filtered_db = filtered_db[filtered_db['Owner'] == "1st"]
            elif owner_input == "2nd Owner": filtered_db = filtered_db[filtered_db['Owner'] == "2nd"]
            elif owner_input == "3rd+ Owner": filtered_db = filtered_db[filtered_db['Owner'].isin(["3rd", "4th"])]
        if variant_input.strip() != "":
            filtered_db = filtered_db[filtered_db['Variant'].str.contains(variant_input, case=False, na=False)]

        st.session_state.scraped_data = filtered_db.to_dict('records')
        st.session_state.scan_complete = True

if st.session_state.scan_complete:
    scraped_data = st.session_state.scraped_data
    
    if len(scraped_data) > 0:
        parsed_prices = [car["Price_Raw"] for car in scraped_data]
        avg_retail_price = sum(parsed_prices) // len(parsed_prices)
        
        target_profit_amount = int(avg_retail_price * (target_margin / 100))
        max_buying_price = avg_retail_price - target_profit_amount - safe_refurb_cost
        
        actual_profit_at_asking = avg_retail_price - customer_asking_price - safe_refurb_cost
        actual_margin_pct = (actual_profit_at_asking / avg_retail_price) * 100 if avg_retail_price > 0 else 0
        negotiation_gap = customer_asking_price - max_buying_price

        # 🎈 SAAS ANIMATION TRIGGER: If it's a massively profitable deal, celebrate!
        if actual_margin_pct >= target_margin and actual_margin_pct > 5:
            st.balloons()
            st.toast("🎉 Highly Profitable Deal Detected!", icon="🔥")

        col1, col2, col3 = st.columns(3)
        with col1: 
            st.metric("Recommended Max Bid", format_inr(max_buying_price), "Your absolute ceiling", delta_color="normal")
        with col2: 
            st.metric("Expected Retail Value", format_inr(avg_retail_price), "Market Baseline", delta_color="off")
        with col3: 
            profit_label = f"Profit at Asking Price ({actual_margin_pct:.1f}%)"
            diff_from_target = actual_profit_at_asking - target_profit_amount
            delta_str = f"{format_inr(diff_from_target)} vs Target Margin"
            st.metric(profit_label, format_inr(actual_profit_at_asking), delta_str, delta_color="normal")

        if negotiation_gap > 0:
            st.warning(f"⚠️ **Negotiate Down.** The asking price ({format_inr(customer_asking_price)}) reduces your margin to {actual_margin_pct:.1f}%. Talk them down by **{format_inr(negotiation_gap)}** to hit your {target_margin}% goal.")
        else:
            st.success(f"✅ **Clear to Buy.** The asking price ({format_inr(customer_asking_price)}) clears your {target_margin}% margin hurdle. Proceed with acquisition.")

        st.divider()
        st.markdown("#### Competitor Analysis & Market Plot")
        
        df = pd.DataFrame(scraped_data)
        fig = px.scatter(df, x="Kilometer", y="Price_Lakhs", color="Source", hover_data=["Variant", "Reg_Year", "Listing_Date", "Date_Found"], template="plotly_dark")
        fig.add_scatter(x=[65000], y=[round(max_buying_price/100000, 2)], mode="markers+text", marker=dict(color="#00C9FF", size=20, symbol="star"), name="MAX BID", text=["★ YOUR BID"], textposition="top center")
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(df, use_container_width=True, hide_index=True)
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("⬇️ Export SaaS Report to Excel/CSV", data=csv, file_name=f"DealerIntel_{brand}_{model}.csv", mime="text/csv")
    else:
        st.error(f"🚨 No inventory match. Turn 'Deep Web Scan' ON to query live APIs.")