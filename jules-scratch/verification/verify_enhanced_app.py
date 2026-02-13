from playwright.sync_api import sync_playwright

def run_verification():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # Navigate to the Streamlit app
            page.goto("http://localhost:8501", timeout=20000)

            # Wait for the page to be relatively stable
            page.wait_for_load_state("networkidle", timeout=10000)

            # Take a screenshot to see what's on the page
            page.screenshot(path="jules-scratch/verification/enhanced_app_debug.png")

        finally:
            browser.close()

if __name__ == "__main__":
    run_verification()