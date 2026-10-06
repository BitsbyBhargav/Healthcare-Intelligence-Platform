import joblib
from pathlib import Path

from model import decision_threshold, rf_model, scaler

output_dir = Path(__file__).resolve().parent
joblib.dump(rf_model, output_dir / "rf_readmission_model.pkl")
joblib.dump(scaler, output_dir / "scaler.pkl")
joblib.dump(decision_threshold, output_dir / "decision_threshold.pkl")