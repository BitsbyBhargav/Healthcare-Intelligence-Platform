"""Genuine Chromium screenshots and browser interaction checks of local Streamlit."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright
R=Path(__file__).resolve().parents[1]; E=R/'deliverables/evidence'; E.mkdir(exist_ok=True)
log=[]
with sync_playwright() as p:
    browser=p.chromium.launch(channel="chrome")
    page=browser.new_page(viewport={'width':1600,'height':1100},device_scale_factor=1)
    errors=[]
    page.on('pageerror',lambda e: errors.append(str(e)))
    page.goto('http://127.0.0.1:8512',wait_until='domcontentloaded')
    page.get_by_text('Clinical Risk Intelligence Studio',exact=True).wait_for(timeout=60000)
    def view(name,title):
        page.get_by_test_id('stSidebar').get_by_text(name,exact=True).click()
        page.get_by_role('heading',name=title,exact=True).wait_for(timeout=30000)
        page.wait_for_timeout(800)
        assert page.locator('[data-testid="stException"]').count()==0
        log.append({'view':name,'status':'passed'})
    view('Association Mining','Association Mining')
    page.get_by_text('FP-Growth',exact=True).click()
    page.wait_for_timeout(500)
    page.screenshot(path=str(E/'01_association.png'))
    page.get_by_text('Frequent patterns',exact=True).click()
    page.wait_for_timeout(500)
    page.screenshot(path=str(E/'01_itemsets.png'))
    page.get_by_text('Frequent patterns',exact=True).click()
    page.locator('[data-testid="stPlotlyChart"]').last.scroll_into_view_if_needed()
    page.wait_for_timeout(400)
    page.screenshot(path=str(E/'01_association_chart.png'))
    slider=page.get_by_role('slider',name='Minimum lift')
    slider.focus(); slider.press('ArrowRight'); page.wait_for_timeout(400)
    view('Model Benchmark','Model Benchmark')
    page.screenshot(path=str(E/'02_benchmark.png'))
    page.get_by_role('combobox').click()
    page.get_by_role('option',name='Accuracy',exact=True).click()
    page.wait_for_timeout(400)
    view('Best Model','Best Model')
    page.screenshot(path=str(E/'03_best_model.png'))
    page.locator('[data-testid="stPlotlyChart"]').last.scroll_into_view_if_needed()
    page.wait_for_timeout(400)
    page.screenshot(path=str(E/'03_best_details.png'))
    view('Clinical Profiling','Clinical Profiling')
    page.get_by_role('combobox').click()
    page.get_by_role('option',name='Length of stay',exact=True).click()
    page.wait_for_timeout(400)
    page.screenshot(path=str(E/'04_profiling.png'))
    view('Live Risk Studio','Live Risk Studio')
    page.get_by_role('button',name='Estimate readmission probabilities').click()
    page.get_by_role('heading',name='Most likely outcome:',exact=False).wait_for(timeout=30000)
    assert page.locator('[data-testid="stException"]').count()==0
    page.get_by_role('heading',name='Most likely outcome:',exact=False).scroll_into_view_if_needed()
    page.screenshot(path=str(E/'05_inference.png'))
    log.append({'interaction':'Saved-model prediction','status':'passed'})
    assert not errors,errors
    (R/'deliverables/logs/browser.json').write_text(json.dumps({'checks':log,'page_errors':errors,'capture':'Chromium viewport screenshots of the running app, no reconstructed UI'},indent=2))
    browser.close()
print(json.dumps(log,indent=2))
