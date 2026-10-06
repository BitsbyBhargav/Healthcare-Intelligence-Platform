import sqlite3
import pandas as pd

conn = sqlite3.connect("healthcare_dw.db")
query = """
SELECT
    f.time_in_hospital, f.num_lab_procedures, f.num_procedures,
    f.num_medications, f.number_diagnoses, p.age, p.gender, p.race, f.readmitted
FROM Fact_Admissions f
JOIN Dim_Patient p ON f.patient_nbr = p.patient_nbr;
"""
df = pd.read_sql_query(query, conn)
conn.close()