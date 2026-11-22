"""Capture the local dashboard and check desktop/mobile layout."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(channel='chrome', headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 2100}, device_scale_factor=1)
        page.goto('http://127.0.0.1:8540')
        page.get_by_text('Better insight. Better planning.', exact=True).wait_for()
        dismiss = page.get_by_text("Don't show again", exact=True)
        if dismiss.count():
            dismiss.click()
        page.screenshot(path=str(ROOT / 'outputs/ui_overview.png'), full_page=True, animations='disabled')
        page.get_by_text('F - Classification implementation', exact=True).click()
        page.get_by_role('button', name='Predict readmission', exact=True).wait_for()
        page.get_by_text('Your prediction will appear here after you submit the patient profile.', exact=True).wait_for()
        page.screenshot(path=str(ROOT / 'outputs/ui_classifier_form.png'), full_page=True, animations='disabled')
        page.get_by_role('button', name='Predict readmission', exact=True).click()
        page.get_by_text('PREDICTED OUTCOME', exact=True).wait_for()
        page.get_by_text('How the model was trained', exact=True).wait_for()
        # Restore the top after Streamlit scrolls to the submitted form.
        page.locator('[data-testid="stMain"]').evaluate('(element) => element.scrollTop = 0')
        page.screenshot(path=str(ROOT / 'outputs/ui_classifier_result.png'), full_page=True, animations='disabled')
        desktop = page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
        assert page.locator('[data-testid="stException"]').count() == 0
        page.set_viewport_size({'width': 390, 'height': 1100})
        sidebar = page.locator('[data-testid="stSidebar"]')
        if sidebar.bounding_box()['x'] >= 0:
            sidebar.get_by_role('button').first.click()
            page.wait_for_function('document.querySelector(\'[data-testid="stSidebar"]\').getBoundingClientRect().right <= 0')
        page.locator('[data-testid="stMain"]').evaluate('(element) => element.scrollTop = 0')
        page.screenshot(path=str(ROOT / 'outputs/ui_mobile.png'), full_page=True, animations='disabled')
        mobile = page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
        assert not desktop and not mobile
        print(json.dumps({'desktop_horizontal_overflow': desktop, 'mobile_horizontal_overflow': mobile, 'browser_exceptions': 0}))
        browser.close()


if __name__ == '__main__':
    main()
