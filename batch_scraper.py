# batch_scraper.py (GitHub Actions ke liye modified)
# Yeh script GitHub Action se keywords ko Environment Variable ke through uthaata hai.

import time
import pandas as pd
import os
import re
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
# NOTE: GitHub Actions mein hum ChromeDriverManager ke bajaye fixed path use karenge
from selenium.common.exceptions import TimeoutException, WebDriverException
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import phonenumbers

# --- CONFIGURATION ---
# GitHub Action yahan par keywords ki list set karega (comma-separated string)
# Agar environment variable set nahi hai to default value use hogi
KEYWORDS_STRING = os.environ.get('KEYWORDS_INPUT', 'restaurant near me, ac repair karachi')
OUTPUT_FOLDER = 'BATCH_SCRAPING_RESULTS' 

# Social media patterns for detection
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
    """Chrome Driver ko GitHub Actions environment ke liye configure karta hai."""
    print("-> Setting up Chrome Driver for Headless Mode...")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')          # Browser ko background (GUI ke bagair) mein chalao
    options.add_argument('--no-sandbox')        # Zaruri hai GitHub Actions/Docker ke liye
    options.add_argument('--disable-dev-shm-usage') # Memory issue ko theek karta hai
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    try:
        # GitHub Actions mein Chromium binary ka path fixed hota hai
        driver = webdriver.Chrome(service=Service('/usr/bin/chromium-browser'), options=options)
        print("-> Driver setup successful.")
        return driver
    except Exception as e:
        print(f"!!! Error setting up driver: {e}")
        return None

def scrape_social_media(website_url):
    """Website se social media links scrape karta hai."""
    social_links = {key: 'N/A' for key in SOCIAL_MEDIA_PATTERNS}
    if website_url in ['N/A', 'No Website']:
        return social_links

    try:
        # Website ka content download karein
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        response = requests.get(website_url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            print(f"    ! Website access failed: Status {response.status_code}")
            return social_links
        
        soup = BeautifulSoup(response.content, 'html.parser')
        html_content = response.text # Plain text content
        
        # 1. HTML content mein links talash karein
        for key, patterns in SOCIAL_MEDIA_PATTERNS.items():
            for pattern in patterns:
                # Regular expression se match karein
                match = re.search(pattern, html_content, re.IGNORECASE)
                if match:
                    # Match ko complete URL mein badalna
                    if not match.group(0).startswith(('http', 'www')):
                        social_links[key] = 'https://' + match.group(0)
                    else:
                        social_links[key] = match.group(0)
                    break # Pehla link milte hi ruk jao

    except requests.exceptions.RequestException as e:
        # print(f"    ! Website request error for {website_url}: {e}")
        pass
    except Exception as e:
        # print(f"    ! General error in social media scraping: {e}")
        pass

    return social_links

def scrape_google_maps(driver, keyword):
    """Google Maps se business leads scrape karta hai."""
    base_url = "https://www.google.com/maps/search/"
    search_url = f"{base_url}{keyword.replace(' ', '+')}"
    print(f"-> Searching for: {keyword}")

    try:
        driver.get(search_url)
        # Wait for the search results container to load
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="feed"]'))
        )
    except TimeoutException:
        print("  ! Timeout while loading search page. Skipping keyword.")
        return []
    except WebDriverException as e:
        print(f"  ! WebDriver error: {e}")
        return []

    business_details = []
    
    # Scroll down to load more results (max 3 scrolls for efficiency)
    for _ in range(3):
        scrollable_div = driver.find_element(By.CSS_SELECTOR, 'div[role="feed"]')
        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
        time.sleep(3) # Wait for new results to load

    # Extract all business cards
    try:
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
            
            # Click on the card to open the details panel
            card.click()
            
            # Wait for the details panel to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-ogc-title]'))
            )
            
            # Extract details from the new panel
            details = {'Business Name': name}
            
            # Extract Category, Rating, Reviews
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
            
            # Extract Address, Phone, Website
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

            # Close the details panel to go back to the list
            try:
                close_button = driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Close"]')
                close_button.click()
                time.sleep(1) # Wait for the map to reset
            except:
                # If close button is not found, refresh the page to reset
                driver.get(search_url)
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="feed"]'))
                )
                
        except Exception as e:
            # print(f"  ! Error processing a card: {e}")
            pass

    return business_details


# --- MAIN EXECUTION ---
if __name__ == '__main__':
    # Keywords string ko list mein badalna (comma-separated)
    keywords = [k.strip() for k in KEYWORDS_STRING.split(',') if k.strip()]
    
    if not keywords:
        print("!!! ERROR: No keywords found in KEYWORDS_INPUT environment variable.")
    else:
        print(f"\n--- STARTING BATCH SCRAPING ---")
        print(f"Keywords to process: {len(keywords)}")
        
        # Output folder banana
        if not os.path.exists(OUTPUT_FOLDER):
            os.makedirs(OUTPUT_FOLDER)
        
        driver = setup_driver()
        if not driver:
            exit(1)

        for keyword in keywords:
            all_business_details = scrape_google_maps(driver, keyword)
            
            if all_business_details:
                df = pd.DataFrame(all_business_details)
                
                # Column order with social media
                column_order = [
                    'Business Name', 'Website', 'Phone Number', 'Rating', 'Reviews', 
                    'Category', 'Address', 'Facebook', 'Instagram', 'Twitter', 
                    'LinkedIn', 'YouTube', 'Pinterest', 'TikTok'
                ]
                
                # Only include columns that exist in the dataframe
                existing_columns = [col for col in column_order if col in df.columns]
                df = df.reindex(columns=existing_columns)
                
                # File ka naam keyword ke hisab se banayein
                safe_filename = "".join(c for c in keyword if c.isalnum() or c in (' ', '_')).rstrip()
                output_path = os.path.join(OUTPUT_FOLDER, f"leads_{safe_filename}.csv")
                
                df.to_csv(output_path, index=False, encoding='utf-8-sig')
                print(f"  -> SUCCESS: Saved {len(all_business_details)} leads to '{output_path}'")
            else:
                print(f"  ! Could not scrape any details for keyword '{keyword}'.")

            # Har keyword ke baad ek lamba break lein
            print("  -> Taking a short break before the next keyword...")
            time.sleep(15)

        driver.quit()
        print("\n\n--- BATCH PROCESS COMPLETE! ---")
        print(f"All keywords have been processed. Results committed to GitHub.")
