# batch_scraper.py (GitHub Actions ke liye Fixed)
# यह स्क्रिप्ट GitHub Action से कीवर्ड्स को Environment Variable के माध्यम से उठाती है।

import time
import pandas as pd
import os
import re
import requests
import sys # FIX: Clean exit के लिए sys को import करें
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service 
from selenium.common.exceptions import TimeoutException, WebDriverException
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import phonenumbers

# --- CONFIGURATION ---
# GitHub Action यहाँ पर keywords की list सेट करेगा (comma-separated string)
KEYWORDS_STRING = os.environ.get('KEYWORDS_INPUT', 'restaurant near me, ac repair karachi')
OUTPUT_FOLDER = 'BATCH_SCRAPING_RESULTS' 

# सोशल मीडिया पैटर्न (पहचान के लिए)
SOCIAL_MEDIA_PATTERNS = {
    'facebook': [r'facebook\.com/[^/\\s\\?]+', r'fb\.com/[^/\\s\\?]+'],
    'instagram': [r'instagram\.com/[^/\\s\\?]+', r'instagr\.am/[^/\\s\\?]+'],
    'twitter': [r'twitter\.com/[^/\\s\\?]+', r'x\.com/[^/\\s\\?]+'],
    'linkedin': [r'linkedin\.com/company/[^/\\s\\?]+', r'linkedin\.com/in/[^/\\s\\?]+'],
    'youtube': [r'youtube\.com/(channel|user)/[^/\\s\\?]+', r'youtu\.be/[^/\\s\\?]+'],
    'pinterest': [r'pinterest\.com/[^/\\s\\?]+'],
    'tiktok': [r'tiktok\.com/[^/\\s\\?]+']
}

# --- FUNCTIONS ---

def setup_driver():
    """Chrome Driver को GitHub Actions environment के लिए कॉन्फ़िगर करता है।"""
    print("-> Chrome Driver को Headless Mode के लिए सेट अप किया जा रहा है...")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')          # ब्राउज़र को पृष्ठभूमि (background) में चलाएँ
    options.add_argument('--no-sandbox')        # GitHub Actions/Docker के लिए ज़रूरी है
    options.add_argument('--disable-dev-shm-usage') # मेमोरी समस्या को ठीक करता है
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    try:
        # FIX: अब ड्राइवर system PATH में 'chromedriver' को ढूंढेगा, जिसे YAML फ़ाइल install करेगी
        driver = webdriver.Chrome(options=options)
        print("-> ड्राइवर सेटअप सफल रहा।")
        return driver
    except Exception as e:
        print(f"!!! ड्राइवर सेटअप में त्रुटि: {e}")
        return None

def scrape_social_media(website_url):
    """वेबसाइट से सोशल मीडिया लिंक्स स्क्रैप करता है।"""
    social_links = {key: 'N/A' for key in SOCIAL_MEDIA_PATTERNS}
    if website_url in ['N/A', 'No Website']:
        return social_links

    try:
        # वेबसाइट का कंटेंट डाउनलोड करें
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        response = requests.get(website_url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return social_links
        
        soup = BeautifulSoup(response.content, 'html.parser')
        html_content = response.text 
        
        # 1. HTML कंटेंट में लिंक्स तलाश करें
        for key, patterns in SOCIAL_MEDIA_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, html_content, re.IGNORECASE)
                if match:
                    if not match.group(0).startswith(('http', 'www')):
                        social_links[key] = 'https://' + match.group(0)
                    else:
                        social_links[key] = match.group(0)
                    break 

    except requests.exceptions.RequestException as e:
        pass
    except Exception as e:
        pass

    return social_links

def scrape_google_maps(driver, keyword):
    """Google Maps से व्यापार (business) leads स्क्रैप करता है।"""
    base_url = "https://www.google.com/maps/search/"
    search_url = f"{base_url}{keyword.replace(' ', '+')}"
    print(f"-> खोज जारी है: {keyword}")

    try:
        driver.get(search_url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="feed"]'))
        )
    except TimeoutException:
        print("  ! खोज पेज लोड होने में समय लगा। यह कीवर्ड छोड़ा जा रहा है।")
        return []
    except WebDriverException as e:
        print(f"  ! WebDriver त्रुटि: {e}")
        return []

    business_details = []
    
    # अधिक परिणाम लोड करने के लिए नीचे स्क्रॉल करें (दक्षता के लिए अधिकतम 3 स्क्रॉल)
    for _ in range(3):
        scrollable_div = driver.find_element(By.CSS_SELECTOR, 'div[role="feed"]')
        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
        time.sleep(3) 

    # सभी व्यापार कार्ड निकालें
    try:
        cards = driver.find_elements(By.CSS_SELECTOR, 'div[role="feed"] > div > div[jsaction^="mouseover:"][aria-label]')
        print(f"  -> {len(cards)} संभावित कार्ड मिले।")
    except:
        print("  ! परिणाम कार्ड नहीं मिल सके।")
        return []

    # प्रत्येक कार्ड को प्रोसेस करें
    for card in cards:
        try:
            name_element = card.find_element(By.CLASS_NAME, 'fontHeadlineSmall')
            name = name_element.text.strip()
            
            # विवरण पैनल खोलने के लिए कार्ड पर क्लिक करें
            card.click()
            
            # विवरण पैनल के लोड होने का इंतजार करें
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-ogc-title]'))
            )
            
            # नए पैनल से विवरण निकालें
            details = {'Business Name': name}
            
            # श्रेणी (Category), रेटिंग, समीक्षाएँ (Reviews) निकालें
            try:
                details['Category'] = driver.find_element(By.CSS_SELECTOR, 'button[jsaction*="category"]').text.strip()
            except:
                details['Category'] = 'N/A'
                
            try:
                rating_text = driver.find_element(By.CSS_SELECTOR, 'div.fontDisplayLarge').text.strip()
                details['Rating'] = float(rating_text)
            except:
                details['Rating'] = 'N/A'
                
            try:
                reviews_text = driver.find_element(By.CSS_SELECTOR, 'button[jsaction*="toggleReviews"]').text.strip()
                details['Reviews'] = reviews_text.replace(' reviews', '').replace(' Review', '').replace('(', '').replace(')', '').strip()
            except:
                details['Reviews'] = 'N/A'
            
            # पता (Address), फ़ोन, वेबसाइट निकालें
            info_elements = driver.find_elements(By.CSS_SELECTOR, 'button[data-tooltip]')
            
            details['Address'] = 'N/A'
            details['Phone Number'] = 'N/A'
            details['Website'] = 'No Website'
            
            for info in info_elements:
                tooltip = info.get_attribute('data-tooltip')
                text = info.text.strip()
                
                if tooltip == 'Address':
                    details['Address'] = text
                elif tooltip == 'Phone':
                    details['Phone Number'] = text
                elif tooltip == 'Website':
                    details['Website'] = text
            
            # --- सोशल मीडिया स्क्रैपिंग ---
            social_links = scrape_social_media(details['Website'])
            details.update(social_links)
            
            business_details.append(details)
            print(f"  -> स्क्रैप किया गया: {name}")

            # सूची पर वापस जाने के लिए विवरण पैनल बंद करें
            try:
                close_button = driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Close"]')
                close_button.click()
                time.sleep(1) 
            except:
                # यदि बंद करने का बटन नहीं मिलता है, तो रीसेट करने के लिए पेज को रीफ़्रेश करें
                driver.get(search_url)
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="feed"]'))
                )
                
        except Exception as e:
            pass

    return business_details


# --- MAIN EXECUTION ---
if __name__ == '__main__':
    keywords = [k.strip() for k in KEYWORDS_STRING.split(',') if k.strip()]
    
    if not keywords:
        print("!!! त्रुटि: KEYWORDS_INPUT environment variable में कोई कीवर्ड नहीं मिला।")
    else:
        print(f"\n--- बैच स्क्रैपिंग शुरू हो रही है ---")
        print(f"प्रोसेस करने के लिए कीवर्ड्स: {len(keywords)}")
        
        if not os.path.exists(OUTPUT_FOLDER):
            os.makedirs(OUTPUT_FOLDER)
        
        driver = setup_driver()
        if not driver:
            # FIX: exit(1) की जगह sys.exit(1) का प्रयोग करें
            sys.exit(1)

        for keyword in keywords:
            all_business_details = scrape_google_maps(driver, keyword)
            
            if all_business_details:
                df = pd.DataFrame(all_business_details)
                
                column_order = [
                    'Business Name', 'Website', 'Phone Number', 'Rating', 'Reviews', 
                    'Category', 'Address', 'Facebook', 'Instagram', 'Twitter', 
                    'LinkedIn', 'YouTube', 'Pinterest', 'TikTok'
                ]
                
                existing_columns = [col for col in column_order if col in df.columns]
                df = df.reindex(columns=existing_columns)
                
                safe_filename = "".join(c for c in keyword if c.isalnum() or c in (' ', '_')).rstrip()
                output_path = os.path.join(OUTPUT_FOLDER, f"leads_{safe_filename}.csv")
                
                df.to_csv(output_path, index=False, encoding='utf-8-sig')
                print(f"  -> सफलता: '{output_path}' में {len(all_business_details)} leads सहेजी गईं")
            else:
                print(f"  ! कीवर्ड '{keyword}' के लिए कोई विवरण स्क्रैप नहीं हो सका।")

            print("  -> अगले कीवर्ड से पहले थोड़ा ब्रेक ले रहे हैं...")
            time.sleep(15)

        driver.quit()
        print("\n\n--- बैच प्रोसेस पूरा हुआ! ---")
        print(f"सभी कीवर्ड्स प्रोसेस हो चुके हैं। परिणाम GitHub पर commit कर दिए गए हैं।")
