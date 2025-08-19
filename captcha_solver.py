from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import pandas as pd
load_dotenv()
from PIL import Image
import requests
import io
import time
import os
import base64
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import PyPDF2
import pikepdf

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('judgment_downloader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PDFHandler:
    @staticmethod
    def is_valid_pdf(file_path):
        """Check if PDF is readable using PyPDF2"""
        try:
            with open(file_path, 'rb') as f:
                PyPDF2.PdfReader(f)
            return True
        except Exception as e:
            logger.warning(f"Invalid PDF: {file_path} - {str(e)}")
            return False

    @staticmethod
    def decrypt_pdf(input_path, output_path):
        """Remove password protection using pikepdf"""
        try:
            with pikepdf.open(input_path) as pdf:
                pdf.save(output_path)
            logger.info(f"Decrypted PDF: {input_path}")
            return True
        except pikepdf.PasswordError:
            logger.error(f"Password-protected (could not decrypt): {input_path}")
            return False
        except Exception as e:
            logger.error(f"Decryption failed for {input_path}: {str(e)}")
            return False

    @staticmethod
    def repair_pdf(input_path, output_path):
        """Attempt to fix corrupted PDF using pikepdf"""
        try:
            with pikepdf.open(input_path) as pdf:
                pdf.save(output_path)
            logger.info(f"Repaired PDF: {input_path}")
            return True
        except Exception as e:
            logger.error(f"Repair failed for {input_path}: {str(e)}")
            return False

class SupremeCourtJudgmentDownloader:
    def __init__(self, max_captcha_retries=3, max_download_retries=3):
        self.max_captcha_retries = max_captcha_retries
        self.max_download_retries = max_download_retries
        self.driver = None

    def setup_driver(self, headless=True):
        """Initialize Chrome WebDriver with options"""
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--window-size=1920,1080")
        self.driver = webdriver.Chrome(options=chrome_options)
        return WebDriverWait(self.driver, 20)

    def upscale_image(self, image_path, scale_factor=2):
        """Enhance CAPTCHA image quality"""
        img = Image.open(image_path)
        width, height = img.size
        img_resized = img.resize((width * scale_factor, height * scale_factor), Image.LANCZOS)
        buffer = io.BytesIO()
        img_resized.save(buffer, format="PNG")
        return buffer.getvalue()

    def solve_captcha(self, image_path):
        """Solve CAPTCHA using Gemini AI"""
        llm_gemini = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0,
        )
        upscaled_image_bytes = self.upscale_image(image_path, scale_factor=4)
        base64_image = base64.b64encode(upscaled_image_bytes).decode("utf-8")
        
        prompt = """Extract numbers and operators (+/-) from this image. 
        Return ONLY the numerical result (e.g., '7')."""
        
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]
        }]
        return int(llm_gemini.invoke(messages).content.strip())

    def download_pdf(self, url, save_path):
        """Download PDF with retries and validation"""
        for attempt in range(self.max_download_retries):
            try:
                response = requests.get(url, verify=False, timeout=30)
                response.raise_for_status()
                
                # Save the file temporarily
                temp_path = f"{save_path}.temp"
                with open(temp_path, 'wb') as f:
                    f.write(response.content)
                
                # Validate PDF
                if PDFHandler.is_valid_pdf(temp_path):
                    os.rename(temp_path, save_path)
                    logger.info(f"Successfully downloaded: {save_path}")
                    return True
                else:
                    # Attempt repair
                    repaired_path = f"{save_path}.repaired"
                    if PDFHandler.repair_pdf(temp_path, repaired_path):
                        if PDFHandler.is_valid_pdf(repaired_path):
                            os.rename(repaired_path, save_path)
                            logger.info(f"Repaired and saved: {save_path}")
                            return True
                    
                    # Attempt decryption if repair failed
                    decrypted_path = f"{save_path}.decrypted"
                    if PDFHandler.decrypt_pdf(temp_path, decrypted_path):
                        if PDFHandler.is_valid_pdf(decrypted_path):
                            os.rename(decrypted_path, save_path)
                            logger.info(f"Decrypted and saved: {save_path}")
                            return True
                
                # Cleanup temp files
                for fpath in [temp_path, repaired_path, decrypted_path]:
                    if os.path.exists(fpath):
                        os.remove(fpath)
                
                raise ValueError("PDF validation failed after repair attempts")
            
            except Exception as e:
                logger.warning(f"Attempt {attempt+1} failed for {url}: {str(e)}")
                time.sleep(2)
        
        logger.error(f"Permanently failed to download: {url}")
        return False

    def process_month(self, year, month):
        """Download judgments for a specific month"""
        start_date = f"01{month:02d}{year}"
        last_day = 31 if month in [1,3,5,7,8,10,12] else 30 if month != 2 else 29 if year % 4 == 0 else 28
        end_date = f"{last_day}{month:02d}{year}"
        
        logger.info(f"\n{'='*50}\nProcessing {datetime(year, month, 1).strftime('%B %Y')}\n{'='*50}")
        
        wait = self.setup_driver(headless=True)  # Set to True for production
        try:
            self.driver.get("https://www.sci.gov.in/judgements-judgement-date/")
            
            # Set date range
            wait.until(EC.element_to_be_clickable((By.ID, 'from_date'))).send_keys(start_date)
            wait.until(EC.element_to_be_clickable((By.ID, 'to_date'))).send_keys(end_date)
            time.sleep(2)

            # CAPTCHA handling
            for attempt in range(self.max_captcha_retries):
                try:
                    captcha_img = wait.until(EC.presence_of_element_located((By.ID, "siwp_captcha_image_0")))
                    captcha_src = captcha_img.get_attribute("src")
                    
                    with open("captcha_temp.png", "wb") as f:
                        f.write(requests.get(captcha_src, verify=False, timeout=10).content)
                    
                    solution = self.solve_captcha("captcha_temp.png")
                    logger.info(f"CAPTCHA attempt {attempt+1}: {solution}")
                    
                    wait.until(EC.element_to_be_clickable((By.ID, "siwp_captcha_value_0"))).send_keys(str(solution))
                    self.driver.find_element(By.NAME, "submit").click()
                    time.sleep(3)
                    
                    if "Invalid Captcha" not in self.driver.page_source:
                        break
                except Exception as e:
                    logger.error(f"CAPTCHA error: {str(e)}")
                    if attempt == self.max_captcha_retries - 1:
                        raise

            # Process results
            wait.until(EC.presence_of_element_located((By.XPATH, "//table//tbody/tr")))
            time.sleep(2)
            
            rows = self.driver.find_elements(By.XPATH, "//table//tbody/tr")
            logger.info(f"Found {len(rows)} cases")
            
            for idx, row in enumerate(rows, 1):
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) < 8:
                        continue
                    
                    case_number = cells[2].text.strip().replace('/', '_')
                    petitioner = cells[3].find_element(By.TAG_NAME, "div").text.strip()
                    
                    os.makedirs(f"judgments/{year}/{month:02d}", exist_ok=True)
                    
                    for link in cells[7].find_elements(By.XPATH, './/a[contains(@href, ".pdf")]'):
                        pdf_url = link.get_attribute("href")
                        if not pdf_url.lower().endswith(".pdf"):
                            continue
                            
                        pdf_name = f"{case_number}_{link.text.strip()[:50].replace(' ', '_')}.pdf"
                        pdf_path = f"judgments/{year}/{month:02d}/{pdf_name}"
                        
                        if not self.download_pdf(pdf_url, pdf_path):
                            continue
                
                except Exception as e:
                    logger.error(f"Error in row {idx}: {str(e)}")

        except Exception as e:
            logger.error(f"Error processing {start_date} to {end_date}: {str(e)}")
            self.driver.save_screenshot(f"error_{year}_{month}.png")
        finally:
            if os.path.exists("captcha_temp.png"):
                os.remove("captcha_temp.png")
            if self.driver:
                self.driver.quit()

    def download_range(self, start_year=1950, start_month=1, end_year=2025, end_month=7):
        """Download judgments for a date range"""
        current_date = datetime(start_year, start_month, 1)
        end_date = datetime(end_year, end_month, 1)
        
        while current_date <= end_date:
            self.process_month(current_date.year, current_date.month)
            
            # Move to next month
            if current_date.month == 12:
                current_date = datetime(current_date.year + 1, 1, 1)
            else:
                current_date = datetime(current_date.year, current_date.month + 1, 1)

if __name__ == "__main__":
    downloader = SupremeCourtJudgmentDownloader(
        max_captcha_retries=3,
        max_download_retries=3
    )
    downloader.download_range(start_year=2018, start_month=9, end_year=2018, end_month=10)





    