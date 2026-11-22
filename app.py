"""Launch with: python -m streamlit run app.py"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'jury_2_dw'))

from healthline.ui import main

main()
