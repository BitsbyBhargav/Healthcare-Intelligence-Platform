"""Actual local-browser smoke test and unaltered screenshots for HealthLine."""
from pathlib import Path
import json
import time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'deliverables/healthline_evidence'
OUT.mkdir(exist_ok=True)
checks=[]
for attempt in range(30):
    try:
        with urlopen('http://127.0.0.1:8530/_stcore/health',timeout=1) as response:
            if response.status==200: break
    except OSError:
        time.sleep(.5)
else:
    raise RuntimeError('Start HealthLine on port 8530 before browser verification')
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome')
    page=browser.new_page(viewport={'width':1500,'height':1100},device_scale_factor=1)
    blocked=[]
    def local_only(route):
        if route.request.url.startswith('http://127.0.0.1:8530/'):
            route.continue_()
        else:
            blocked.append(route.request.url)
            route.abort()
    page.route('**/*',local_only)
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://127.0.0.1:8530',wait_until='domcontentloaded')
    page.get_by_role('heading',name='HealthLine Clinical Analytics',exact=True).wait_for(timeout=60000)
    page.wait_for_timeout(1500)
    def workspace(name):
        page.get_by_test_id('stSidebar').get_by_role('combobox').click()
        page.get_by_role('option',name=name,exact=True).click()
        page.wait_for_timeout(700)
    def view(name):
        page.get_by_test_id('stSidebar').get_by_text(name,exact=True).click()
        page.get_by_role('heading',name=name,exact=True).wait_for(timeout=30000)
        page.wait_for_timeout(500)
        assert page.get_by_test_id('stException').count()==0
        checks.append({'page':name,'status':'passed'})
    view('Executive Overview')
    page.screenshot(path=str(OUT/'01_command_center.png'),full_page=True)
    workspace('Simulation Studio')
    view('Data Pipeline')
    page.get_by_role('button',name='Run Hospital Data Replay',exact=True).click()
    page.get_by_text('Committed. Warehouse and analytics refreshed.',exact=True).wait_for(timeout=60000)
    page.wait_for_timeout(1500)
    page.screenshot(path=str(OUT/'02_pipeline_completed.png'),full_page=True)
    checks.append({'interaction':'Real historical replay committed','status':'passed'})
    view('Warehouse Explorer')
    page.screenshot(path=str(OUT/'03_replay_warehouse.png'),full_page=True)
    workspace('Clinical Analytics')
    view('Patient Segmentation')
    page.get_by_text('Measured segment profiles',exact=True).wait_for(timeout=30000)
    page.screenshot(path=str(OUT/'04_patient_segments.png'),full_page=True)
    view('Readmission Assessment')
    page.get_by_role('button',name='Estimate readmission probabilities',exact=True).click()
    page.get_by_role('heading',name='Most likely outcome:',exact=False).wait_for(timeout=60000)
    page.screenshot(path=str(OUT/'05_discharge_risk.png'),full_page=True)
    checks.append({'interaction':'Saved three-class model inference','status':'passed'})
    workspace('Simulation Studio')
    view('Capacity Scenarios')
    page.get_by_role('button',name='Save hypothetical scenario',exact=True).click()
    page.get_by_text('Hypothetical scenario saved separately from clinical records.',exact=True).wait_for()
    page.screenshot(path=str(OUT/'06_scenario.png'),full_page=True)
    workspace('Clinical Analytics')
    view('System Evidence')
    page.screenshot(path=str(OUT/'07_architecture.png'),full_page=True)
    assert not errors,errors
    (OUT/'browser_checks.json').write_text(json.dumps({'checks':checks,'page_errors':errors,
        'external_http_blocked':True,'blocked_request_count':len(blocked),
        'capture':'Actual Chrome screenshots of local Streamlit; no reconstructed UI'},indent=2))
    browser.close()
print(json.dumps(checks,indent=2))
