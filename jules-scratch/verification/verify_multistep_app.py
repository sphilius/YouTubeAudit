from playwright.sync_api import sync_playwright, expect

def run_verification():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # Navigate to the Streamlit app
            page.goto("http://localhost:8501", timeout=20000)

            # Wait for the main title to be visible to ensure the page has loaded
            expect(page.get_by_role("heading", name="YouTube Topic Audit Engine")).to_be_visible(timeout=10000)

            # Verify that the new Step 1 button is present
            expect(page.get_by_role("button", name="1. Load and Parse My Files")).to_be_visible()

            # Take a screenshot
            page.screenshot(path="jules-scratch/verification/multistep_app_verification.png")

        finally:
            browser.close()

if __name__ == "__main__":
    run_verification()