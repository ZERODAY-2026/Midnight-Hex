-- ==============================================================================
-- DataMind: Snowflake Setup Script
-- Role, Warehouse, and Read-Only Least-Privilege Grants
-- ==============================================================================

-- 1. Create a dedicated X-Small warehouse with aggressive auto-suspend
-- This minimizes credit consumption on Snowflake trial accounts (suspends after 60s idle).
CREATE WAREHOUSE IF NOT EXISTS DATAMIND_WH
  WAREHOUSE_SIZE = XSMALL
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Dedicated warehouse for DataMind conversational SQL queries';

-- 2. Create the dedicated read-only role
CREATE ROLE IF NOT EXISTS DATAMIND_READONLY
  COMMENT = 'Read-only access role for DataMind natural language agent';

-- 3. Grant warehouse usage to the role
GRANT USAGE ON WAREHOUSE DATAMIND_WH TO ROLE DATAMIND_READONLY;

-- 4. Grant access to the Snowflake Sample Data database
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE_SAMPLE_DATA TO ROLE DATAMIND_READONLY;

-- 5. Grant role to your user (replace <your_user> with your active Snowflake username)
-- Example: GRANT ROLE DATAMIND_READONLY TO USER JAHANVII;
-- GRANT ROLE DATAMIND_READONLY TO USER <your_user>;
