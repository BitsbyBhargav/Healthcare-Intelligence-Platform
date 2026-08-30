import sqlite3
import io
import json
import urllib.request
from pathlib import Path
import pandas as pd


UCI_DATASET_ID = 296
UCI_TIMEOUT_SECONDS = 30
DATA_PATH = Path(__file__).resolve().parent.parent / 'data' / 'diabetes_130_us.csv'


def load_diabetes_dataset():
    """Download the dataset with a timeout and return feature/target frames."""
    api_url = f'https://archive.ics.uci.edu/api/dataset?id={UCI_DATASET_ID}'
    try:
        with urllib.request.urlopen(api_url, timeout=UCI_TIMEOUT_SECONDS) as response:
            metadata = json.load(response)['data']
        with urllib.request.urlopen(metadata['data_url'], timeout=UCI_TIMEOUT_SECONDS) as response:
            original = pd.read_csv(io.BytesIO(response.read()), low_memory=False)
    except Exception as error:
        raise RuntimeError(
            f'Unable to download UCI dataset within {UCI_TIMEOUT_SECONDS} seconds. '
            'Check your internet connection or download the dataset locally.'
        ) from error

    target_columns = [variable['name'] for variable in metadata['variables']
                      if variable['role'] == 'Target']
    return original.drop(columns=target_columns), original[target_columns]

print("Step 1: Extracting Raw Healthcare Data from UCI Repository...")
# Fetch Diabetes 130-US Hospitals dataset (Repository ID: 296)
X, y = load_diabetes_dataset()

# Combine features and target variable into a single dataframe
df = pd.concat([X, y], axis=1)

# Ensure a patient identifier exists; create a surrogate if missing
if 'patient_nbr' not in df.columns:
    df['patient_nbr'] = df.index + 1

# Save raw fetched dataset physically into the data folder
df.to_csv(DATA_PATH, index=False)
print(f"Raw dataset saved to {DATA_PATH}")

print("Step 2: Performing ETL Transformations and Cleaning Data...")
# Replace missing character markers with Null values
df.replace('?', None, inplace=True)

# Generate unique surrogate IDs for encounter tracking
df['encounter_id'] = df.index + 1000

# Build Dim_Patient table
dim_patient = df[['patient_nbr', 'race', 'gender', 'age']].drop_duplicates(subset=['patient_nbr'])

# Build Dim_Admission table
dim_admission = df[['admission_type_id', 'discharge_disposition_id', 'admission_source_id']].drop_duplicates()
dim_admission['admission_id'] = range(1, len(dim_admission) + 1)

# Map admission_id foreign keys back to central dataframe
df = df.merge(dim_admission, on=['admission_type_id', 'discharge_disposition_id', 'admission_source_id'], how='left')

# Build Dim_Diagnosis table
dim_diagnosis = df[['diag_1', 'diag_2', 'medical_specialty']].drop_duplicates()
dim_diagnosis['diag_id'] = range(1, len(dim_diagnosis) + 1)

# Map diag_id foreign keys back to central dataframe
df = df.merge(dim_diagnosis, on=['diag_1', 'diag_2', 'medical_specialty'], how='left')

# Build Fact_Admissions table
fact_admissions = df[[
    'encounter_id', 'patient_nbr', 'admission_id', 'diag_id',
    'time_in_hospital', 'num_lab_procedures', 'num_procedures',
    'num_medications', 'number_diagnoses', 'readmitted'
]]

print("Step 3: Loading Fact and Dimension Tables into SQLite Data Warehouse...")
# Connect to SQLite Database (Creates database file: healthcare_dw.db)
conn = sqlite3.connect('healthcare_dw.db')

# Load DataFrames into relational tables
dim_patient.to_sql('Dim_Patient', conn, if_exists='replace', index=False)
dim_admission.to_sql('Dim_Admission', conn, if_exists='replace', index=False)
dim_diagnosis.to_sql('Dim_Diagnosis', conn, if_exists='replace', index=False)
fact_admissions.to_sql('Fact_Admissions', conn, if_exists='replace', index=False)

print("Data Warehouse pipeline execution completed successfully.\n")


# OLAP Query Execution Engine
def execute_olap_query(title, sql_query):
    print(f"==================================================")
    print(f"OLAP OPERATION: {title}")
    print(f"==================================================")
    query_result = pd.read_sql_query(sql_query, conn)
    print(query_result.head(10))
    print("\n")

# OLAP Operation 1: Roll-Up (Aggregating stay duration across patient age groups)
rollup_query = """
SELECT 
    p.age, 
    COUNT(f.encounter_id) AS total_admissions,
    ROUND(AVG(f.time_in_hospital), 2) AS avg_days_stay
FROM Fact_Admissions f
JOIN Dim_Patient p ON f.patient_nbr = p.patient_nbr
GROUP BY p.age
ORDER BY total_admissions DESC;
"""
execute_olap_query("Roll-Up (Admissions & Average Stay by Age Group)", rollup_query)

# OLAP Operation 2: Slice (Filtering readmission rates for high-medication patients)
slice_query = """
SELECT 
    f.readmitted,
    COUNT(f.encounter_id) AS patient_count,
    ROUND(AVG(f.num_lab_procedures), 1) AS avg_lab_tests
FROM Fact_Admissions f
WHERE f.num_medications > 15
GROUP BY f.readmitted;
"""
execute_olap_query("Slice (Readmission Metrics for Patients with > 15 Medications)", slice_query)

# Close database connection
conn.close()