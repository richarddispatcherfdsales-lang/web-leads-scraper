# batch_scraper.py (GitHub Actions Final Fixed Version)
# This script retrieves keywords from a GitHub Action Environment Variable.

import time
import pandas as pd
import os
import re
import requests
import sys 
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
# GitHub Action will set the list of keywords here (comma-separated string)
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
    """Configures the Chrome Driver for the GitHub Actions environment."""
    print("-> Setting up Chrome Driver for Headless Mode...")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')          # Run browser in background
    options.add_argument('--no-sandbox')        # Required for GitHub Actions/Docker
    options.add_argument('--disable-dev-shm-usage') # Fixes memory issue
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # 🌟 CRITICAL FIX: Tell Selenium where the Chromium browser binary is located.
    # This path matches the 'chromium-browser' package installed in the YAML.
    options.binary_location = '/usr/bin/chromium-browser' 
    
    try:
        # The YAML file ensures 'chromedriver' is in the system PATH.
        driver = webdriver.Chrome(options=options)
        print("-> Driver setup successful.")
        return driver
    except Exception as e:
        print(f"!!! Driver setup error: {e}")
        # Clean exit on failure
        return None

def scrape_social_media(website_url):
    """Scrapes social media links from the website."""
    social_links = {key: 'N/A' for key in SOCIAL_MEDIA_PATTERNS}
    if website_url in ['N/A', 'No Website']:
        return social_links

    try:
        # Download website content
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        response = requests.get(website_url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return social_links
        
        soup = BeautifulSoup(response.content, 'html.parser')
        html_content = response.text 
        
        # 1. Look for links in HTML content
        for key, patterns in SOCIAL_MEDIA_PATTERMS.items():
            for pattern in patterns:
                match = re.search(pattern, html_content, re.IGNORECASE)
                if match:
                    # Clean up the link (add https if missing)
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
    # Note: Using a modified base URL to help prevent immediate blocks
    base_url = "https://www.google.com/maps/search/"
    search_url = f"{base_url}{keyword.replace(' ', '+')}"
    print(f"-> Search initiated: {keyword}")

    try:
        driver.get(search_url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="feed"]'))
        )
    except TimeoutException:
        print("  ! Search page took too long to load. Skipping keyword.")
        return []
    except WebDriverException as e:
        print(f"  ! WebDriver Error: {e}")
        return []

    business_details = []
    
    # Scroll down to load more results (max 3 scrolls for efficiency)
    for _ in range(3):
        scrollable_div = driver.find_element(By.CSS_SELECTOR, 'div[role="feed"]')
        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
        time.sleep(3) 

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
            
            # Click the card to open the details panel
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
                # Clean up the reviews count (e.g., "1,234 reviews" -> "1,234")
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

            # Close the details panel to return to the list
            try:
                close_button = driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Close"]')
                close_button.click()
                time.sleep(1) 
            except:
                # If close button is not found, refresh the page to reset the state
                driver.get(search_url)
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="feed"]'))
                )
                
        except Exception:
            # Skip to the next card if processing fails for any reason
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
            # sys.exit(1) is called inside setup_driver() if it fails, 
            # but we keep this check for redundancy.
            sys.exit(1)

        for keyword in keywords:
            all_business_details = scrape_google_maps(driver, keyword)
            
            if all_business_details:
                df = pd.DataFrame(all_business_details)
                
                # Define desired column order
                column_order = [
                    'Business Name', 'Website', 'Phone Number', 'Rating', 'Reviews', 
                    'Category', 'Address', 'Facebook', 'Instagram', 'Twitter', 
                    'LinkedIn', 'YouTube', 'Pinterest', 'TikTok'
                ]
                
                # Filter columns to only include existing ones and reorder
                existing_columns = [col for col in column_order if col in df.columns]
                df = df.reindex(columns=existing_columns)
                
                # Create a safe filename from the keyword
                safe_filename = "".join(c for c in keyword if c.isalnum() or c in (' ', '_')).rstrip()
                output_path = os.path.join(OUTPUT_FOLDER, f"leads_{safe_filename}.csv")
                
                df.to_csv(output_path, index=False, encoding='utf-8-sig')
                print(f"  -> SUCCESS: Saved {len(all_business_details)} leads to '{output_path}'")
            else:
                print(f"  ! Could not scrape any details for keyword '{keyword}'.")

            print("  -> Taking a short break before the next keyword...")
            time.sleep(15)

        driver.quit()
        print("\n\n--- BATCH PROCESS COMPLETE! ---")
        print(f"All keywords have been processed. The results have been committed back to the repository.")
