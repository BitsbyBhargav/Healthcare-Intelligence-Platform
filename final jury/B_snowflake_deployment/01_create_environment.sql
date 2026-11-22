-- Final jury: manual Snowflake environment setup.
-- Execute in a SQL worksheet. These statements do not replace existing objects.

USE ROLE SYSADMIN;

CREATE WAREHOUSE IF NOT EXISTS FINAL_JURY_WH
    WAREHOUSE_TYPE = 'STANDARD'
    WAREHOUSE_SIZE = 'XSMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'Final jury healthcare data loading and analytical queries';

CREATE DATABASE IF NOT EXISTS HEALTHCARE_FINAL_JURY
    COMMENT = 'Final jury UCI and SPARCS integrated healthcare warehouse';

CREATE SCHEMA IF NOT EXISTS HEALTHCARE_FINAL_JURY.STAGING
    COMMENT = 'Source-aligned modelled data before dimensional transformation';

CREATE SCHEMA IF NOT EXISTS HEALTHCARE_FINAL_JURY.DW
    COMMENT = 'Dimensional warehouse facts, dimensions and analytical views';

USE WAREHOUSE FINAL_JURY_WH;
USE DATABASE HEALTHCARE_FINAL_JURY;
USE SCHEMA DW;

-- Verify the environment and capture results for Block B evidence.
SHOW WAREHOUSES LIKE 'FINAL_JURY_WH';
SHOW DATABASES LIKE 'HEALTHCARE_FINAL_JURY';
SHOW SCHEMAS IN DATABASE HEALTHCARE_FINAL_JURY;

SELECT CURRENT_ROLE() AS ACTIVE_ROLE,
       CURRENT_WAREHOUSE() AS ACTIVE_WAREHOUSE,
       CURRENT_DATABASE() AS ACTIVE_DATABASE,
       CURRENT_SCHEMA() AS ACTIVE_SCHEMA;
