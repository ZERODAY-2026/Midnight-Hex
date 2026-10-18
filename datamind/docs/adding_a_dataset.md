# Adding a New Dataset to DataMind (Zero-Code Reusability)

DataMind is architected from the ground up to be **dataset-agnostic**. Adding a new database, schema, or industry domain does **not** require modifying Python code, prompt strings, or agent logic. All dataset behavior is governed by declarative YAML configuration files in `configs/`.

This design satisfies **Criterion 7 (Reusability & Adaptability)** of the Hackathon rubric.

---

## 1. The Dataset Configuration Anatomy

Every dataset configuration file in `configs/<name>.yaml` defines five key elements:

```yaml
# 1. Snowflake Database and Schema Coordinates
database: YOUR_DATABASE
schema: YOUR_SCHEMA
max_rows: 500  # Enforced upper limit on query results

# 2. Whitelisted Tables and Column Annotations
tables:
  SALES_RECORDS:
    description: "Transactional retail purchase history"
    columns:
      TX_ID: "Unique transaction identifier"
      CUSTOMER_ID: "Foreign key to CUSTOMERS.ID"
      TOTAL_AMOUNT: "Transaction amount in USD"
      TX_DATE: "Timestamp when transaction completed"

# 3. Canonical Joins (Explicit relationships for multi-table queries)
joins:
  - SALES_RECORDS.CUSTOMER_ID = CUSTOMERS.ID

# 4. Business Definitions & Domain Glossary
glossary:
  revenue: "SUM(TOTAL_AMOUNT)"
  high_value_customer: "CUSTOMERS with SUM(TOTAL_AMOUNT) > 10000"
  active_period: "TX_DATE >= '2023-01-01'"
```

---

## 2. Step-by-Step Guide: Adding a Custom Dataset

### Step 1: Create or Load Data into Snowflake
Run your DDL and data load scripts in a Snowflake worksheet. For instance, see `sql/load_second_dataset.sql` for how the secondary **Our World in Data (OWID)** dataset was created.

Ensure the `DATAMIND_READONLY` role has `SELECT` privileges on the new schema:
```sql
GRANT USAGE ON DATABASE YOUR_DATABASE TO ROLE DATAMIND_READONLY;
GRANT USAGE ON SCHEMA YOUR_DATABASE.YOUR_SCHEMA TO ROLE DATAMIND_READONLY;
GRANT SELECT ON ALL TABLES IN SCHEMA YOUR_DATABASE.YOUR_SCHEMA TO ROLE DATAMIND_READONLY;
```

### Step 2: Create `configs/<your_dataset>.yaml`
Create a new YAML file inside `configs/`. For example, `configs/retail.yaml` or `configs/owid.yaml`.

Fill in:
- The exact table names.
- Column descriptions to guide Gemma on business semantics.
- Allowed joins.
- Key business metric formulas in the `glossary` section.

### Step 3: Select the Dataset in DataMind UI
1. Launch the Streamlit application:
   ```bash
   streamlit run app/streamlit_app.py
   ```
2. In the sidebar dropdown, select your newly registered dataset.
3. DataMind immediately queries Snowflake's `INFORMATION_SCHEMA` for the new schema, merges it with your YAML descriptions, and starts answering questions using Gemma and Snowflake!

---

## 3. Case Study: Our World in Data (OWID)

DataMind includes a fully configured second dataset out of the box:
- Configuration: `configs/owid.yaml`
- SQL Setup: `sql/load_second_dataset.sql`

Try asking:
- *"Which countries had the highest renewable energy share in 2022?"*
- *"Compare CO2 emissions between United States and China over time"*
- *"What is the cleanest country in terms of renewable percentage?"*

DataMind seamlessly switches from retail/supply-chain TPC-H data to global macroeconomic climate indicators purely through configuration!
