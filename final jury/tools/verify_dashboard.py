"""Check A-J navigation and manual predictions against saved held-out results."""
from pathlib import Path
import json
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from complete_analytics import features, NUM, CAT
import joblib
import pandas as pd
from streamlit.testing.v1 import AppTest


def main():
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=60).run()
    assert not app.exception, str(app.exception)
    pages = list(app.radio[0].options)
    checked = []
    for page in pages:
        app.radio[0].set_value(page).run()
        assert not app.exception, f'{page}: {app.exception}'
        checked.append(page)
    app.radio[0].set_value(pages[5]).run()
    assert len(app.selectbox) == 11 and len(app.number_input) == 8
    assert all(widget.label != 'UCI example row' for widget in app.number_input)
    model = joblib.load(ROOT / 'outputs/classification/selected_pipeline.joblib')
    categories = dict(zip(CAT, model.named_steps['prepare'].named_transformers_['categorical'].categories_))
    saved = pd.read_parquet(ROOT / 'outputs/classification/test_predictions.parquet')
    raw = pd.read_parquet(ROOT / 'data/processed/uci_supervised.parquet')
    records = raw.merge(saved[['encounter_id', 'Random Forest']], on='encounter_id', validate='one_to_one')
    prepared = features(records)
    selectable = pd.Series(True, index=prepared.index)
    for field in CAT:
        selectable &= prepared[field].isin(categories[field])
    cases = []
    # Exercise all output classes using independent, previously saved test predictions.
    for outcome in ['NO', '>30', '<30']:
        index = records.index[selectable & records['Random Forest'].eq(outcome)][0]
        values = prepared.loc[index]
        for field in NUM:
            app.number_input(key='manual_' + field).set_value(int(values[field]))
        for field in CAT:
            app.selectbox(key='manual_' + field).set_value(values[field])
        app.button[0].click().run()
        assert not app.exception, str(app.exception)
        result = app.session_state['manual_prediction']
        assert result['class'] == outcome, (result, outcome)
        assert abs(sum(result['probabilities'].values()) - 1) < 1e-10
        for field in NUM + CAT:
            assert result['inputs'][field] == values[field], field
        cases.append({'encounter_id': str(records.loc[index, 'encounter_id']), 'expected': outcome, 'actual': result['class']})
    report = {'status': 'passed', 'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
              'pages_checked': checked, 'manual_fields': 19, 'golden_test_predictions': cases,
              'checks': ['All ten pages render without Streamlit exceptions',
                         'All 19 manual controls reach the pipeline unchanged',
                         'Three manually entered held-out profiles reproduce saved predictions for all output classes',
                         'All submitted probability distributions sum to one']}
    (ROOT / 'outputs/dashboard_validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
