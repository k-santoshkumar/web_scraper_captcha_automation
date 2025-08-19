# Supreme Court Judgment Downloader & CAPTCHA Automation

Automatically downloads Supreme Court judgments and solves CAPTCHAs using Gemini AI and web scraping.

## Features

- **Automated CAPTCHA Solver:** Uses Gemini AI to solve numerical CAPTCHAs with operators.
- **Judgment Downloader:** Scrapes and downloads PDF judgments from the Supreme Court of India by specified date range.
- **PDF Validation & Repair:** Validates, repairs, and decrypts corrupted or password-protected PDFs using PyPDF2 and pikepdf.
- **Headless Automation:** Uses Selenium with Chrome WebDriver in headless mode for reliability.
- **Logging:** All actions and errors are logged for easy troubleshooting.

## Requirements

- Python 3.8+
- Chrome and ChromeDriver installed
- Gemini AI API key (via environment variables)
- Required Python packages (see below)

## Installation

```bash
pip install -r requirements.txt
```

Required Python packages (add these to your `requirements.txt` if not present):

```
selenium
requests
PyPDF2
pikepdf
Pillow
python-dotenv
langchain-google-genai
pandas
```

## How It Works

1. The script launches a headless Chrome browser.
2. Navigates to the Supreme Court judgment search page.
3. For each month in the date range:
    - Sets the date range and fetches results.
    - Handles CAPTCHA using Gemini AI (by upscaling and extracting the solution).
    - Downloads available PDF judgments.
    - Validates, repairs, and decrypts PDFs as needed.
4. All downloads and actions are logged.

## Usage

Edit and run the main script:

```python
if __name__ == "__main__":
    downloader = SupremeCourtJudgmentDownloader(
        max_captcha_retries=3,
        max_download_retries=3
    )
    downloader.download_range(start_year=2018, start_month=9, end_year=2018, end_month=10)
```

- Change `start_year`, `start_month`, `end_year`, `end_month` as needed.
- PDFs are saved under `judgments/{year}/{month}/`.

## CAPTCHA Solving

- The CAPTCHA image is upscaled to improve recognition.
- Gemini AI is prompted to extract numbers and operators, returning only the final result.
- The result is submitted; if invalid, retries are attempted.

## Environment Variables

Create a `.env` file with your Gemini AI API key and other secrets as needed:

```
GOOGLE_API_KEY=your_google_api_key
```

## Logging

Logs are saved to `judgment_downloader.log` and printed to the console.

## Troubleshooting

- If ChromeDriver isn't found, ensure it's installed and available in your PATH.
- CAPTCHAs may occasionally fail; increase `max_captcha_retries` if needed.
- Invalid PDFs are automatically repaired or decrypted.


## Disclaimer

This tool is for educational and research purposes only. Use responsibly and respect the terms of service of the target website.
