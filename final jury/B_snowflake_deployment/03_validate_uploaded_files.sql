-- Step 3: run after all nine .csv.gz packages are uploaded at stage root.
-- Validation reads the files and returns errors WITHOUT loading the table.
USE ROLE SYSADMIN;
USE WAREHOUSE FINAL_JURY_WH;
USE DATABASE HEALTHCARE_FINAL_JURY;
USE SCHEMA STAGING;

LIST @HEALTHCARE_FINAL_JURY.STAGING.MODELLED_STAGE;

COPY INTO HEALTHCARE_FINAL_JURY.STAGING.MODELLED_RAW
FROM @HEALTHCARE_FINAL_JURY.STAGING.MODELLED_STAGE
FILES = (
    'modelled_part_001.csv.gz',
    'modelled_part_002.csv.gz',
    'modelled_part_003.csv.gz',
    'modelled_part_004.csv.gz',
    'modelled_part_005.csv.gz',
    'modelled_part_006.csv.gz',
    'modelled_part_007.csv.gz',
    'modelled_part_008.csv.gz',
    'modelled_part_009.csv.gz'
)
FILE_FORMAT = (FORMAT_NAME = 'HEALTHCARE_FINAL_JURY.STAGING.MODELLED_CSV_FORMAT')
VALIDATION_MODE = 'RETURN_ALL_ERRORS';

-- Expected validation result: zero error rows. Stop on any reported error.
