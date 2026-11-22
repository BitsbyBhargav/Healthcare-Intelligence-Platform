-- Step 4: execute ONLY after step 3 returns zero validation errors.
-- Loading history skips the same files on a normal repeat execution.
USE ROLE SYSADMIN;
USE WAREHOUSE FINAL_JURY_WH;
USE DATABASE HEALTHCARE_FINAL_JURY;
USE SCHEMA STAGING;

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
ON_ERROR = ABORT_STATEMENT
FORCE = FALSE
PURGE = FALSE;

-- Expected: nine file results with LOADED status and zero errors.
-- Packages 001-008 contain 500,000 rows each; 009 contains 424,257 rows.
SELECT COUNT(*) AS TOTAL_LOADED_ROWS
FROM HEALTHCARE_FINAL_JURY.STAGING.MODELLED_RAW;
-- Expected total: 4,424,257.
