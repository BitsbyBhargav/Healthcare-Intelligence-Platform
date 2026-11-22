"""Generate the manual Snowflake star-schema build and diagram contract."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'B_snowflake_deployment'
manifest=json.loads((ROOT/'A_warehouse_design/data_preparation/modelled_csv_manifest.json').read_text())
columns=[c.upper() for c in manifest['column_names']]
ints={'DISCHARGE_YEAR','LOS_DAYS_LOWER_BOUND','SEVERITY_CODE',*[c.upper() for c in columns if c.startswith('UCI_NUM_') or c.startswith('UCI_NUMBER_')]}
bools={'LOS_TOP_CODED','READMISSION_LABEL_AVAILABLE','IS_SYNTHETIC'}
money={'TOTAL_CHARGES_USD','TOTAL_COSTS_USD'}
def typ(c):
    return 'NUMBER(18,2)' if c in money else 'NUMBER(38,0)' if c in ints else 'BOOLEAN' if c in bools else 'VARCHAR'
def expression(c):
    return f'TRY_TO_NUMBER({c},18,2)' if c in money else f'TRY_TO_NUMBER({c},38,0)' if c in ints else f'TRY_TO_BOOLEAN({c})' if c in bools else c
dims={
 'SOURCE':['SOURCE_KEY','DIABETES_COHORT_DEFINITION'],
 'PERIOD':['PERIOD','DISCHARGE_YEAR'],
 'DEMOGRAPHIC':['SOURCE_KEY','AGE_BAND_RAW','AGE_BAND_COMMON','GENDER','RACE_RAW','ETHNICITY_RAW'],
 'ADMISSION':['SOURCE_KEY','ADMISSION_TYPE_RAW','ADMISSION_TYPE_COMMON','DISPOSITION_RAW','PAYMENT_TYPE','UCI_ADMISSION_SOURCE_ID'],
 'DIAGNOSIS':['SOURCE_KEY','DIAGNOSIS_SYSTEM','DIAGNOSIS_CODE','DIAGNOSIS_DESCRIPTION','APR_DRG_CODE'],
 'FACILITY':['SOURCE_KEY','FACILITY_KEY','FACILITY_NAME','HOSPITAL_COUNTY','SERVICE_AREA'],
 'TREATMENT':['SOURCE_KEY','UCI_INSULIN','UCI_CHANGE','UCI_DIABETESMED','UCI_A1CRESULT','UCI_MAX_GLU_SERUM']}
assigned={}
for name,attrs in dims.items():
    for c in attrs:assigned.setdefault(c,name)
fact_cols=[c for c in columns if c not in assigned]
parts=['''-- Run ALL statements in one Snowflake SQL worksheet.
-- The master CSV and STAGING.MODELLED_RAW are preserved.
-- This build is for the fixed, verified 4,424,257-row jury snapshot.
USE ROLE SYSADMIN;
USE WAREHOUSE FINAL_JURY_WH;
USE DATABASE HEALTHCARE_FINAL_JURY;
USE SCHEMA DW;

-- First result should contain 4,424,257 total and unique keys.
SELECT COUNT(*) AS RAW_ROWS, COUNT(DISTINCT ENCOUNTER_KEY) AS UNIQUE_KEYS
FROM STAGING.MODELLED_RAW;
''']
parts.append('CREATE TRANSIENT TABLE IF NOT EXISTS ETL_ENCOUNTER_TYPED AS\nSELECT\n'+',\n'.join('    '+expression(c)+' AS '+c for c in columns)+'\nFROM STAGING.MODELLED_RAW;')
statements=[]
for name,attrs in dims.items():
    table='DIM_'+name;key=name+'_ID'
    create=f'CREATE TABLE IF NOT EXISTS {table} (\n    {key} NUMBER(38,0) NOT NULL PRIMARY KEY,\n'+',\n'.join(f'    {c} {typ(c)}' for c in attrs)+'\n);'
    order=', '.join(c+' NULLS FIRST' for c in attrs)
    insert=f'INSERT INTO {table}\nSELECT ROW_NUMBER() OVER (ORDER BY {order}) AS {key}, '+', '.join(attrs)+f'\nFROM (SELECT DISTINCT '+', '.join(attrs)+f' FROM ETL_ENCOUNTER_TYPED)\nWHERE NOT EXISTS (SELECT 1 FROM {table});'
    parts.extend([create,insert]);statements.extend([create,insert])
fact_definition=[f'    {name}_ID NUMBER(38,0) NOT NULL REFERENCES DIM_{name}({name}_ID)' for name in dims]
fact_definition += [f'    {c} {typ(c)}'+(' NOT NULL PRIMARY KEY' if c=='ENCOUNTER_KEY' else '') for c in fact_cols]
create='CREATE TABLE IF NOT EXISTS FACT_ENCOUNTER (\n'+',\n'.join(fact_definition)+'\n);'
joins=[]
for i,(name,attrs) in enumerate(dims.items()):
    alias='d'+str(i)
    joins.append(f'LEFT JOIN DIM_{name} {alias} ON '+' AND '.join(f'EQUAL_NULL(s.{c},{alias}.{c})' for c in attrs))
select=[f'd{i}.{name}_ID' for i,name in enumerate(dims)]+['s.'+c for c in fact_cols]
insert='INSERT INTO FACT_ENCOUNTER\nSELECT '+', '.join(select)+'\nFROM ETL_ENCOUNTER_TYPED s\n'+'\n'.join(joins)+'\nWHERE NOT EXISTS (SELECT 1 FROM FACT_ENCOUNTER);'
parts.extend([create,insert]);statements.extend([create,insert])
view_joins=[f'JOIN DIM_{name} d{i} ON f.{name}_ID=d{i}.{name}_ID' for i,name in enumerate(dims)]
aliases={name:'d'+str(i) for i,name in enumerate(dims)}
select=[(aliases[assigned[c]]+'.'+c if c in assigned else 'f.'+c)+' AS '+c for c in columns]
view='CREATE OR REPLACE VIEW V_ENCOUNTER_ANALYTICS AS\nSELECT\n'+',\n'.join('    '+x for x in select)+'\nFROM FACT_ENCOUNTER f\n'+'\n'.join(view_joins)+';'
parts.append(view);statements.append(view)
summary='''CREATE OR REPLACE VIEW V_SOURCE_SUMMARY AS
SELECT SOURCE_KEY, COUNT(*) AS RECORDS,
       COUNT(READMISSION_LABEL) AS KNOWN_READMISSION_LABELS,
       AVG(CASE WHEN NOT LOS_TOP_CODED THEN LOS_DAYS_LOWER_BOUND END) AS AVG_UNCAPPED_LOS_DAYS,
       SUM(TOTAL_COSTS_USD) AS TOTAL_ESTIMATED_COST_USD
FROM V_ENCOUNTER_ANALYTICS GROUP BY SOURCE_KEY;
'''
parts.append(summary);statements.append(summary)
checks=[("Fact rows",'(SELECT COUNT(*) FROM FACT_ENCOUNTER)',4424257),
        ("Unique fact keys",'(SELECT COUNT(DISTINCT ENCOUNTER_KEY) FROM FACT_ENCOUNTER)',4424257),
        ("Joined view rows",'(SELECT COUNT(*) FROM V_ENCOUNTER_ANALYTICS)',4424257),
        ("UCI rows","(SELECT COUNT(*) FROM V_ENCOUNTER_ANALYTICS WHERE SOURCE_KEY='UCI_DIABETES')",101766),
        ("SPARCS 2023 rows","(SELECT COUNT(*) FROM V_ENCOUNTER_ANALYTICS WHERE SOURCE_KEY='SPARCS_2023')",2125754),
        ("SPARCS 2024 rows","(SELECT COUNT(*) FROM V_ENCOUNTER_ANALYTICS WHERE SOURCE_KEY='SPARCS_2024')",2196737),
        ("Labeled rows",'(SELECT COUNT(*) FROM FACT_ENCOUNTER WHERE READMISSION_LABEL_AVAILABLE)',101766),
        ("Invented SPARCS labels","(SELECT COUNT(*) FROM V_ENCOUNTER_ANALYTICS WHERE SOURCE_KEY LIKE 'SPARCS%' AND READMISSION_LABEL IS NOT NULL)",0),
        ("Synthetic rows",'(SELECT COUNT(*) FROM FACT_ENCOUNTER WHERE IS_SYNTHETIC)',0),
        ("Real test encounters","(SELECT COUNT(*) FROM FACT_ENCOUNTER WHERE MODEL_ROLE='TEST_LABELED')",19861)]
for name in dims:
    checks.append((f'Duplicate DIM_{name} IDs',f'(SELECT COUNT(*)-COUNT(DISTINCT {name}_ID) FROM DIM_{name})',0))
    checks.append((f'Orphan {name} keys',f'(SELECT COUNT(*) FROM FACT_ENCOUNTER f LEFT JOIN DIM_{name} d ON f.{name}_ID=d.{name}_ID WHERE d.{name}_ID IS NULL)',0))
invalid=' OR '.join(f'(r.{c} IS NOT NULL AND t.{c} IS NULL)' for c in columns if c in ints|bools|money)
checks.append(('Invalid typed source values',f'(SELECT COUNT(*) FROM STAGING.MODELLED_RAW r JOIN ETL_ENCOUNTER_TYPED t ON r.ENCOUNTER_KEY=t.ENCOUNTER_KEY WHERE {invalid})',0))
unions=[]
for label,expr,expected in checks:
    unions.append(f"SELECT '{label}' AS CHECK_NAME, {expr} AS ACTUAL, {expected} AS EXPECTED")
quality='CREATE OR REPLACE VIEW V_WAREHOUSE_CHECKS AS\nSELECT *, CASE WHEN ACTUAL=EXPECTED THEN \'PASS\' ELSE \'FAIL\' END AS STATUS FROM (\n'+'\nUNION ALL\n'.join(unions)+'\n);'
parts.append(quality);statements.append(quality)
parts.extend(['SELECT * FROM V_WAREHOUSE_CHECKS ORDER BY STATUS, CHECK_NAME;',
'''-- Final result must show PASS, 4,424,257 fact rows, 7 dimensions, and zero failed checks.
SELECT CASE WHEN (SELECT COUNT(*) FROM V_WAREHOUSE_CHECKS WHERE STATUS='FAIL')=0
       THEN 'PASS' ELSE 'FAIL' END AS WAREHOUSE_STATUS,
       (SELECT COUNT(*) FROM FACT_ENCOUNTER) AS FACT_ROWS,
       7 AS DIMENSION_TABLES,
       (SELECT COUNT(*) FROM V_WAREHOUSE_CHECKS WHERE STATUS='FAIL') AS FAILED_CHECKS;'''])
sql='\n\n'.join(parts)+'\n'
(OUT/'06_build_dimensional_warehouse.sql').write_text(sql,encoding='utf-8')
(OUT/'07_demo_queries.sql').write_text('''USE ROLE SYSADMIN;
USE WAREHOUSE FINAL_JURY_WH;
USE DATABASE HEALTHCARE_FINAL_JURY;
USE SCHEMA DW;
SELECT * FROM V_SOURCE_SUMMARY ORDER BY SOURCE_KEY;
SELECT SOURCE_KEY, AGE_BAND_COMMON, ADMISSION_TYPE_COMMON, COUNT(*) AS ENCOUNTERS,
 AVG(CASE WHEN NOT LOS_TOP_CODED THEN LOS_DAYS_LOWER_BOUND END) AS AVG_UNCAPPED_STAY
FROM V_ENCOUNTER_ANALYTICS GROUP BY 1,2,3 ORDER BY ENCOUNTERS DESC LIMIT 20;
SELECT AGE_BAND_COMMON, READMISSION_LABEL, COUNT(*) AS ENCOUNTERS
FROM V_ENCOUNTER_ANALYTICS WHERE SOURCE_KEY='UCI_DIABETES'
AND MODEL_ROLE <> 'EXCLUDED_READMISSION_COHORT' GROUP BY 1,2 ORDER BY 1,2;
SELECT SOURCE_KEY,FACILITY_NAME,COUNT(*) AS ENCOUNTERS,SUM(TOTAL_COSTS_USD) AS ESTIMATED_COST
FROM V_ENCOUNTER_ANALYTICS WHERE SOURCE_KEY LIKE 'SPARCS%' AND FACILITY_KEY IS NOT NULL
GROUP BY 1,2 ORDER BY ESTIMATED_COST DESC LIMIT 15;
SELECT * FROM V_WAREHOUSE_CHECKS ORDER BY STATUS,CHECK_NAME;
''',encoding='utf-8')
contract={'dimensions':dims,'fact_columns':fact_cols,'grain':'One published source encounter/discharge record',
          'schema':'Star schema; 7 dimensions and FACT_ENCOUNTER','fact_primary_key':'ENCOUNTER_KEY',
          'total_records':4424257,'execution_status':'Prepared locally; Snowflake user execution pending'}
(ROOT/'A_warehouse_design/star_schema_contract.json').write_text(json.dumps(contract,indent=2),encoding='utf-8')
diagram=['erDiagram']
for name in dims:diagram.append(f'    DIM_{name} ||--o{{ FACT_ENCOUNTER : "{name}_ID"')
(ROOT/'A_warehouse_design/star_schema.mmd').write_text('\n'.join(diagram)+'\n',encoding='utf-8')
import sys
sys.path.insert(0,str(ROOT/'.vendor'))
import sqlglot
for statement in statements:sqlglot.parse(statement,read='snowflake',error_level='RAISE')
print('Generated and parsed dimensional build:',len(statements),'statements; 7 dimensions; all 51 columns represented.')
assert set(assigned)|set(fact_cols)==set(columns)
