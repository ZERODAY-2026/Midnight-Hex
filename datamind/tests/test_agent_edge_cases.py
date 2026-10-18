"""Unit tests for DataMind edge cases, ambiguity, unsupported requests, and grounding."""

import pytest
from unittest.mock import MagicMock, patch
from datamind.models import AgentResult
from datamind.explain import numbers_grounded
from datamind.config import load_config
from datamind.agent import answer
from datamind.gemma_client import _mock_gemma_response
from datamind.prompts import build_system
from datamind.snowflake_client import SnowflakeClient
from datamind.conversation import reset_dataset_conversation
from datamind.schema import build_schema_text


def test_numbers_grounded_success():
    rows = [["AFRICA", 5], ["AMERICA", 5], ["EUROPE", 5]]
    # Numbers 5 and 3 (count of regions) or values in table
    answer = "There are 5 nations in AFRICA and 5 nations in AMERICA."
    assert numbers_grounded(answer, rows) is True


def test_numbers_grounded_hallucination_detected():
    rows = [["AFRICA", 5], ["AMERICA", 5]]
    # 99 is hallucinated
    answer = "There are 99 nations in AFRICA and 5 in AMERICA."
    assert numbers_grounded(answer, rows) is False


def test_numbers_grounded_empty_rows():
    assert numbers_grounded("No matching records were found.", []) is True
    # If hallucinated positive number is present when rows are empty:
    assert numbers_grounded("Found 42 orders.", []) is False


def test_config_loader():
    cfg_tpch = load_config("configs/tpch.yaml")
    assert cfg_tpch.database == "SNOWFLAKE_SAMPLE_DATA"
    assert "ORDERS" in cfg_tpch.tables
    assert len(cfg_tpch.joins) >= 3

    cfg_owid = load_config("configs/owid.yaml")
    assert cfg_owid.database == "DATAMIND_DB"
    assert "ENERGY_CONSUMPTION" in cfg_owid.tables


@patch("datamind.agent.ask_json")
def test_agent_clarify_flow(mock_ask):
    mock_ask.return_value = {
        "status": "clarify",
        "clarification": "Do you mean orders in 1995 or 1996?",
        "assumptions": ["Date filter missing"]
    }
    cfg = load_config("configs/tpch.yaml")
    sf = MagicMock()

    res = answer("Show me top orders", cfg, sf, "schema_text")
    assert res["type"] == "clarify"
    assert "1995 or 1996" in res["message"]


@patch("datamind.agent.ask_json")
def test_agent_unsupported_flow(mock_ask):
    mock_ask.return_value = {
        "status": "unsupported",
        "message": "Forecasting future order volumes is not supported."
    }
    cfg = load_config("configs/tpch.yaml")
    sf = MagicMock()

    res = answer("Predict tomorrow's order sales", cfg, sf, "schema_text")
    assert res["type"] == "unsupported"
    assert "Forecasting" in res["message"]


@patch("datamind.agent.ask_json")
def test_agent_empty_results_flow(mock_ask):
    mock_ask.return_value = {
        "status": "ok",
        "sql": "SELECT * FROM ORDERS WHERE O_ORDERDATE = '2099-01-01'",
        "assumptions": ["Future date filter"]
    }
    cfg = load_config("configs/tpch.yaml")
    sf = MagicMock()
    sf.run.return_value = {"columns": ["O_ORDERKEY"], "rows": [], "query_id": "sfqid-empty-001"}

    res = answer("Show orders from year 2099", cfg, sf, "schema_text")
    assert res["type"] == "empty"
    assert res["query_id"] == "sfqid-empty-001"
    assert "returned no matching records" in res["message"]


@patch("datamind.agent.ask_json")
def test_agent_auto_repair_loop(mock_ask):
    # First attempt returns invalid SQL (unallowed table)
    # Second attempt (fix) returns valid SQL
    mock_ask.side_effect = [
        {"status": "ok", "sql": "SELECT * FROM FORBIDDEN_TABLE", "assumptions": []},
        {"status": "ok", "sql": "SELECT COUNT(*) FROM ORDERS"},
        {"answer": "Total orders are 1500000.", "how": "Counted ORDERS table rows."}
    ]
    cfg = load_config("configs/tpch.yaml")
    sf = MagicMock()
    sf.run.return_value = {"columns": ["COUNT(*)"], "rows": [[1500000]], "query_id": "sfqid-repair-002"}

    res = answer("How many orders?", cfg, sf, "schema_text", retries=1)
    assert res["type"] == "ok"
    assert "ORDERS" in res["sql"]
    assert res["grounded"] is True


def test_demo_generator_routes_to_the_selected_dataset():
    tpch_cfg = load_config("configs/tpch.yaml")
    owid_cfg = load_config("configs/owid.yaml")

    tpch_plan = _mock_gemma_response(
        build_system(tpch_cfg, "Table: ORDERS"),
        "Question: How many total orders are there?",
    )
    owid_plan = _mock_gemma_response(
        build_system(owid_cfg, "Table: ENERGY_CONSUMPTION"),
        "Question: What is energy consumption per country?",
    )

    assert "FROM ORDERS" in tpch_plan["sql"]
    assert "FROM ENERGY_CONSUMPTION" in owid_plan["sql"]
    assert "ORDERS" not in owid_plan["sql"]


@patch("datamind.agent.ask_json")
def test_agent_repair_uses_active_dataset_and_rejects_cross_dataset_sql(mock_ask):
    mock_ask.side_effect = [
        {"status": "ok", "sql": "SELECT * FROM ORDERS"},
        {"status": "ok", "sql": "SELECT * FROM ENERGY_CONSUMPTION"},
        {"answer": "The simulated result is available.", "how": "Read the selected dataset."},
    ]
    cfg = load_config("configs/owid.yaml")
    sf = MagicMock()
    sf.demo_mode = False
    sf.run.return_value = {
        "columns": ["COUNTRY"],
        "rows": [["Example"]],
        "query_id": "sfqid-energy-001",
    }
    schema_text = "Database: DATAMIND_DB\nSchema: OWID\nTable: ENERGY_CONSUMPTION"

    res = answer("Show energy consumption", cfg, sf, schema_text, retries=1)

    assert res["type"] == "ok"
    assert "ENERGY_CONSUMPTION" in res["sql"]
    assert "ORDERS" not in res["sql"]
    assert "Table: ENERGY_CONSUMPTION" in mock_ask.call_args_list[0].args[0]
    repair_prompt = mock_ask.call_args_list[1].args[1]
    assert "Active dataset: DATAMIND_DB.OWID" in repair_prompt
    assert "Allowed tables: ENERGY_CONSUMPTION" in repair_prompt
    assert "ORDERS" not in repair_prompt.split("Active dataset schema:", 1)[1].split("Question:", 1)[0]
    sf.run.assert_called_once()


@patch("datamind.agent.ask_json")
def test_agent_does_not_retry_the_original_query_if_repair_has_no_sql(mock_ask):
    mock_ask.side_effect = [
        {"status": "ok", "sql": "SELECT * FROM ORDERS"},
        {"status": "ok"},
    ]
    cfg = load_config("configs/owid.yaml")
    sf = MagicMock()
    sf.demo_mode = False

    res = answer("Show energy consumption", cfg, sf, "Table: ENERGY_CONSUMPTION", retries=1)

    assert res["type"] == "error"
    assert "did not return a new query" in res["message"]
    sf.run.assert_not_called()


def test_missing_snowflake_credentials_select_simulation_mode(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "")
    monkeypatch.setenv("SNOWFLAKE_USER", "")
    monkeypatch.setenv("SNOWFLAKE_PASSWORD", "")
    monkeypatch.setenv("DATAMIND_DEMO_MODE", "false")

    sf = SnowflakeClient(database="DATAMIND_DB", schema="OWID")

    assert sf.demo_mode is True
    assert "credentials are missing" in sf.demo_reason
    result = sf.run("SELECT * FROM ENERGY_CONSUMPTION")
    assert result["query_id"].startswith("simulation-")
    assert result["rows"] == [["No live Snowflake query was executed."]]


def test_owid_demo_answer_is_dataset_scoped_and_marked_simulated(monkeypatch):
    monkeypatch.setenv("DATAMIND_DEMO_MODE", "false")
    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "")
    monkeypatch.setenv("SNOWFLAKE_USER", "")
    monkeypatch.setenv("SNOWFLAKE_PASSWORD", "")
    cfg = load_config("configs/owid.yaml")
    sf = SnowflakeClient(database=cfg.database, schema=cfg.schema_)
    schema_text = build_schema_text(cfg, sf)

    res = answer(
        "What is energy consumption per country?",
        cfg,
        sf,
        schema_text,
    )

    assert res["type"] == "ok"
    assert res["simulated"] is True
    assert "ENERGY_CONSUMPTION" in res["sql"]
    assert "ORDERS" not in res["sql"]
    assert "no Snowflake data was queried" in res["answer"]


def test_dataset_change_clears_history_answers_and_queued_question():
    state = {
        "active_dataset": "configs/tpch.yaml",
        "history": ["User: Old orders question", "Agent: Old answer"],
        "responses": [{"query": "Old orders question", "result": {"answer": "Old answer"}}],
        "prompt_input": "Old queued question",
    }

    reset_dataset_conversation(state, "configs/owid.yaml")

    assert state["active_dataset"] == "configs/owid.yaml"
    assert state["history"] == []
    assert state["responses"] == []
    assert "prompt_input" not in state


def test_live_client_refuses_to_simulate_without_connection():
    sf = SnowflakeClient.__new__(SnowflakeClient)
    sf.demo_mode = False
    sf.conn = None

    with pytest.raises(RuntimeError, match="refusing to simulate a live query"):
        sf.run("SELECT * FROM ENERGY_CONSUMPTION")
