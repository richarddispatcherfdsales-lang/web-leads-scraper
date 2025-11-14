# batch_scraper.py (GitHub Actions Final Fixed Version - Ultimate Anti-Bot Edition)
# This script retrieves keywords from a GitHub Action Environment Variable.

import time
import pandas as pd
import os
import re
import requests
import sys 
import random # Naya import: Random delays ke liye
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
KEYWORDS_STRING = os.environ.get('KEYWORDS_INPUT', 'restaurant near me, ac repair karachi')
OUTPUT_FOLDER = 'BATCH_SCRAPING_RESULTS' 

# Social media patterns (unchanged)
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
    """Configures the Chrome Driver for the GitHub Actions environment with anti-detection."""
    print("-> Setting up Chrome Driver for Headless Mode with anti-bot measures...")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')          
    options.add_argument('--no-sandbox')        
    options.add_argument('--disable-dev-shm-usage') 
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Chromium Binary Location 
    options.binary_location = '/usr/bin/chromium-browser' 
    
    # Anti-Detection Flags 
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    try:
        driver = webdriver.Chrome(options=options)
        
        # Execute JS to hide additional automation signs
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("-> Driver setup successful with anti-bot flags.")
        return driver
    except Exception as e:
        print(f"!!! Driver setup error: {e}")
        return None

def scrape_social_media(website_url):
    """Scrapes social media links from the website."""
    social_links = {key: 'N/A' for key in SOCIAL_MEDIA_PATTERNS}
    if website_url in ['N/A', 'No Website']:
        return social_links

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        response = requests.get(website_url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return social_links
        
        soup = BeautifulSoup(response.content, 'html.parser')
        html_content = response.text 
        
        for key, patterns in SOCIAL_MEDIA_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, html_content, re.IGNORECASE)
                if match:
                    link = match.group(0)
                    if not link.startswith(('http', 'www')):
                        social_links[key] = 'https://' + link
                    else:
                        social_links[key] = link
                    break 

    except requests.exceptions.RequestException:
        pass
    except Exception:
        pass

    return social_links

def scrape_google_maps(driver, keyword):
    """Scrapes business leads from Google Maps."""
    
    # 🌟 FIX: Use a more direct search URL format for Maps results.
    search_query = keyword.replace(' ', '+')
    search_url = f"https://www.google.com/maps/search/{search_query}" 

    print(f"-> Search initiated: {keyword}")
    print(f"-> URL: {search_url}") 

    try:
        driver.get(search_url)
        # Increased initial wait time (25 seconds)
        WebDriverWait(driver, 25).until( 
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="feed"]'))
        )
    except TimeoutException:
        print("  ! Search page took too long to load (Timeout 25s). It might be blocked. Skipping keyword.")
        return []
    except WebDriverException as e:
        print(f"  ! WebDriver Error: {e}")
        return []

    business_details = []
    
    # Scroll down to load more results (4 scrolls for more data)
    for i in range(4):
        try:
            scrollable_div = driver.find_element(By.CSS_SELECTOR, 'div[role="feed"]')
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
            # 🌟 FIX: Random delay after scrolling to mimic human behavior
            time.sleep(random.uniform(3, 5)) 
        except:
            print(f"  ! Scrolling failed on iteration {i}. Stopping scroll.")
            break

    # Extract all business cards
    try:
        # Business list items ka CSS Selector
        cards = driver.find_elements(By.CSS_SELECTOR, 'div[role="feed"] > div > div[jsaction^="mouseover:"][aria-label]')
        print(f"  -> Found {len(cards)} potential cards.")
    except:
        print("  ! Could not find result cards.")
        return []

    # Process each card
    for card in cards:
        try:
            name_element = card.find_element(By.CLASS_NAME, 'fontHeadlineSmall')
            name = name_element.text.strip()
            
            # Click the card to open the details panel (using robust JS click)
            driver.execute_script("arguments[0].click();", card) 
            
            # 🌟 FIX: Wait thoda zyada (12 seconds) for detail panel to load
            WebDriverWait(driver, 12).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-ogc-title]'))
            )
            
            details = {'Business Name': name}
            
            # Data extraction (using try-except for every piece to ensure stability)
            try:
                details['Category'] = driver.find_element(By.CSS_SELECTOR, 'button[jsaction*="category"]').text.strip()
            except: details['Category'] = 'N/A'
                
            try:
                rating_text = driver.find_element(By.CSS_SELECTOR, 'div.fontDisplayLarge').text.strip()
                details['Rating'] = float(rating_text)
            except: details['Rating'] = 'N/A'
                
            try:
                reviews_text = driver.find_element(By.CSS_SELECTOR, 'button[jsaction*="toggleReviews"]').text.strip()
                details['Reviews'] = reviews_text.replace(' reviews', '').replace(' Review', '').replace('(', '').replace(')', '').strip()
            except: details['Reviews'] = 'N/A'
            
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
            
            # --- Social Media Scraping ---
            social_links = scrape_social_media(details['Website'])
            details.update(social_links)
            
            business_details.append(details)
            print(f"  -> Scraped: {name}")

            # Close the details panel to return to the list
            try:
                close_button = driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Close"]')
                driver.execute_script("arguments[0].click();", close_button)
                time.sleep(1) 
            except:
                # Fallback: Refresh the page to reset the state
                driver.get(search_url)
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="feed"]'))
                )
                
        except Exception as e:
            # Ye exception tab trigger hota hai jab card click karne ke baad detail panel load na ho paye
            print(f"  ! Failed to process card for: {name}. Error: {e}")
            # Ensure we are back on the list view by attempting to close the panel
            try:
                close_button = driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Close"]')
                driver.execute_script("arguments[0].click();", close_button)
                time.sleep(1)
            except:
                pass
            
    return business_details


# --- MAIN EXECUTION ---
if __name__ == '__main__':
    keywords = [k.strip() for k in KEYWORDS_STRING.split(',') if k.strip()]
    
    if not keywords:
        print("!!! ERROR: No keywords found in KEYWORDS_INPUT environment variable.")
        sys.exit(1)
    else:
        print(f"\n--- BATCH SCRAPING STARTING ---")
        print(f"Keywords to process: {len(keywords)}")
        
        if not os.path.exists(OUTPUT_FOLDER):
            os.makedirs(OUTPUT_FOLDER)
        
        driver = setup_driver()
        if not driver:
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
                print(f"  -> SUCCESS: Saved {len(all_business_details)} leads to '{output_path}'")
            else:
                print(f"  ! Could not scrape any details for keyword '{keyword}'.")

            # 🌟 FIX: Random delay between keywords to avoid rate limiting
            print("  -> Taking a random break (15-25s) before the next keyword...")
            time.sleep(random.uniform(15, 25)) 

        driver.quit()
        print("\n\n--- BATCH PROCESS COMPLETE! ---")
        print(f"All keywords have been processed. The results have been committed back to the repository.")
