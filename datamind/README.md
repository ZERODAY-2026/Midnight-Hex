# 🧠 DataMind: Talk to Your Data

> **PS1 — DataMind: Talk to Your Data**  
> *ZeroDay OSS Hacktoberfest 2026 | IIIT Dharwad*  
> An AI-powered analytics system that can query Snowflake in live mode or demonstrate its flow with clearly labeled simulated results, using Google Gemma, deterministic AST guardrails, and claim-to-row numeric checks.

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Data Platform](https://img.shields.io/badge/Snowflake-Enabled-29B5E8.svg)](https://www.snowflake.com/)
[![LLM](https://img.shields.io/badge/Google_Gemma-3n_E4B-4285F4.svg)](https://ollama.com/)
[![Guardrails](https://img.shields.io/badge/Guardrails-sqlglot_AST-success.svg)](https://github.com/tobymao/sqlglot)
[![UI](https://img.shields.io/badge/UI-Streamlit-FF4B4B.svg)](https://streamlit.io/)

---

## 🌟 Overview & Architecture

DataMind bridges the gap between everyday questions and enterprise data warehouses. In live mode, it computes answers from Snowflake, displays the executed query and Snowflake Query ID (`sfqid`), checks numeric claims against retrieved rows, and refuses unsafe or unsupported operations. Without Snowflake credentials—or when demo mode is explicitly enabled—the UI labels placeholder output as simulated and does not present it as verified database data.

```
datamind/
├── README.md                  # Complete project guide and setup instructions
├── requirements.txt           # Python dependencies
├── .env.example               # Environment variables template
├── .gitignore                 # Git ignore file
├── configs/
│   ├── tpch.yaml              # Dataset 1: Snowflake Sample Benchmark (TPC-H SF1)
│   └── owid.yaml              # Dataset 2: Reusability proof (Our World in Data)
├── sql/
│   ├── setup.sql              # Snowflake warehouse, role, and least-privilege grants
│   └── load_second_dataset.sql# Script to create and populate OWID second dataset
├── datamind/
│   ├── __init__.py
│   ├── config.py              # YAML config loader using Pydantic
│   ├── snowflake_client.py    # Snowflake connector, query execution, sfqid tracking
│   ├── schema.py              # INFORMATION_SCHEMA introspection + YAML metadata merger
│   ├── gemma_client.py        # Ollama API client with JSON parsing and cleanups
│   ├── prompts.py             # System prompts, few-shots, business glossary
│   ├── validator.py           # sqlglot AST guardrails (SELECT only, allowed tables, limit)
│   ├── agent.py               # End-to-end orchestrator with auto-repair loop
│   ├── explain.py             # Plain-language explanation & number grounding verification
│   └── models.py              # AgentResult dataclass
├── app/
│   └── streamlit_app.py       # Rich interactive Streamlit UI with Plotly visualizations
├── eval/
│   ├── golden_tpch.yaml       # 35 benchmark questions + ground-truth Snowflake SQL
│   └── run_eval.py            # Automated evaluation script comparing agent vs ground truth
├── tests/
│   ├── test_validator.py      # Pytest suite for SQL guardrails and attack prevention
│   └── test_agent_edge_cases.py # Pytest suite for clarification, empty rows, grounding
└── docs/
    ├── architecture.md        # Comprehensive architecture & rubric alignment
    ├── gemma_deployment.md    # Guide to running Gemma locally via Ollama
    └── adding_a_dataset.md    # Zero-code guide to adding new datasets via YAML
```

---

## 🚀 Quickstart & Setup

### 1. Download & Serve Google Gemma
Install [Ollama](https://ollama.com/) and pull the Google Gemma model:
```bash
ollama pull gemma3n:e4b
```
*(Optionally use `ollama pull gemma2:2b` on low-RAM machines).*

### 2. Python Environment Setup
Create a virtual environment and install dependencies:
```bash
# On Linux / macOS:
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# On Windows (PowerShell):
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Snowflake Setup
1. Log in to your [Snowflake account](https://signup.snowflake.com/) (Trial accounts work seamlessly).
2. Open a new SQL Worksheet and execute [`sql/setup.sql`](file:///sql/setup.sql) to create `DATAMIND_WH` and `DATAMIND_READONLY`.
3. Create your `.env` file from the example:
```bash
# Linux / macOS
cp .env.example .env

# Windows
copy .env.example .env
```
4. Fill in your credentials in `.env`:
```ini
SNOWFLAKE_ACCOUNT=xy12345.us-east-1
SNOWFLAKE_USER=YOUR_USERNAME
SNOWFLAKE_PASSWORD=YOUR_PASSWORD
SNOWFLAKE_ROLE=DATAMIND_READONLY
SNOWFLAKE_WAREHOUSE=DATAMIND_WH

OLLAMA_URL=http://localhost:11434/api/chat
OLLAMA_MODEL=gemma3n:e4b
```

### 4. Run the Streamlit Application
Start the conversational UI:
```bash
streamlit run app/streamlit_app.py
```
Open your browser at `http://localhost:8501`.

### 5. Run the Evaluation Benchmark
Run the automated evaluation benchmark against ground-truth queries:
```bash
python -m eval.run_eval
```

---

## 🛡️ Core Features & Guardrails

| Requirement | Implementation in DataMind | Status |
|---|---|:---:|
| **M1: Natural Language Interaction** | Context-aware translation of business questions to Snowflake SQL | ✅ |
| **M2: Real Data Querying** | Live mode executes queries in Snowflake via `snowflake-connector-python`; demo output is explicitly simulated | ✅ |
| **M3: Grounded Answers** | `numbers_grounded()` checks numeric claims against returned rows; UI distinguishes live rows from placeholders | ✅ |
| **M4: Plain-Language Explanation** | Clear explanation of tables, filters, joins, and assumptions | ✅ |
| **M5: Inspectable Evidence** | Executed SQL, Snowflake Query ID (`sfqid`), tabular data & CSV export | ✅ |
| **M6: Ambiguity & Error Handling** | Clarification questions, unsupported refusal, empty data guidance | ✅ |
| **M7: Meaningful Snowflake & Gemma** | Real separation of Gemma (reasoning) and Snowflake (SQL data execution) | ✅ |
| **M8: Reproducible Open Source** | Tested, documented, and 100% configuration-driven reusability | ✅ |

---

## 🧪 Testing & Quality Assurance

Run the complete test suite with `pytest`:
```bash
pytest -v tests/
```

- `tests/test_validator.py`: Verifies SQL guardrails, syntax checks, rejection of DML/DDL (`DROP`, `DELETE`, `ALTER`), single-statement enforcement, CTE recognition, and LIMIT injection.
- `tests/test_agent_edge_cases.py`: Verifies grounding engine against hallucinations, clarification prompts, unsupported questions, and the auto-repair loop.

---

## 📚 Documentation

- [System Architecture & PS1 Rubric Alignment](docs/architecture.md)
- [Gemma Model Deployment Guide](docs/gemma_deployment.md)
- [Adding a New Dataset via YAML](docs/adding_a_dataset.md)

---

## 📜 License

MIT License. Designed and developed for ZeroDay OSS Hacktoberfest 2026.
