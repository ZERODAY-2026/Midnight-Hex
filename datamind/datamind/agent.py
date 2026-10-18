"""DataMind: Core conversational data agent orchestrator."""

from typing import Any, Dict, List, Optional
from .models import AgentResult
from .config import DatasetCfg
from .snowflake_client import SnowflakeClient
from .gemma_client import ask_json
from .validator import validate, SQLRejected
from .prompts import build_system, EXPLAIN_SYSTEM
from .explain import numbers_grounded


def answer(
    question: str,
    cfg: DatasetCfg,
    sf: SnowflakeClient,
    schema_text: str,
    history: Optional[List[str]] = None,
    retries: int = 2,
) -> AgentResult:
    """
    End-to-end data pipeline:
    1. Gemma translates natural language + history into JSON plan (SQL, assumptions, or clarify/unsupported).
    2. Guardrails validate SQL with sqlglot (SELECT only, allowed tables, limit injection).
    3. Snowflake executes the validated query and returns rows + query ID.
    4. Auto-repair loop retries with error feedback if query validation or execution fails.
    5. Gemma synthesizes a plain-language explanation strictly from the retrieved rows.
    6. Grounding engine checks if all numbers in explanation are substantiated by the data.
    """
    system = build_system(cfg, schema_text)
    simulated = getattr(sf, "demo_mode", False) is True
    ctx = "\n".join(history or [])
    user_prompt = f"{ctx}\nQuestion: {question}" if ctx else f"Question: {question}"

    try:
        plan = ask_json(system, user_prompt, demo_mode=simulated)
    except Exception as e:
        return AgentResult(
            type="error",
            message=f"Model inference failed: {e}",
            simulated=simulated,
        )

    status = plan.get("status", "ok")

    if status == "clarify":
        clarification = plan.get("clarification", "Could you please clarify your request?")
        return AgentResult(
            type="clarify",
            message=clarification,
            assumptions=plan.get("assumptions", []),
            simulated=simulated,
        )

    if status == "unsupported":
        unsupported_msg = plan.get(
            "message",
            "This request cannot be fulfilled with the available dataset (e.g. requires writing data, forecasting, or external metrics)."
        )
        return AgentResult(
            type="unsupported",
            message=unsupported_msg,
            assumptions=plan.get("assumptions", []),
            simulated=simulated,
        )

    allowed_tables = {t.upper() for t in cfg.tables.keys()}
    sql = plan.get("sql", "")
    if not isinstance(sql, str):
        sql = ""
    safe_sql = None
    res = None
    err = None

    if not sql:
        return AgentResult(
            type="error",
            message="Model did not generate a SQL query.",
            assumptions=plan.get("assumptions", []),
            simulated=simulated,
        )

    # Auto-repair loop: validate & execute with iterative correction feedback
    for attempt in range(retries + 1):
        try:
            safe_sql = validate(
                sql,
                allowed_tables,
                cfg.max_rows,
                database=cfg.database,
                schema=cfg.schema_,
            )
            res = sf.run(safe_sql)
            break
        except Exception as e:
            err = str(e)
            if attempt < retries:
                repair_prompt = (
                    f"Active dataset: {cfg.database}.{cfg.schema_}\n"
                    f"Allowed tables: {', '.join(sorted(allowed_tables))}\n"
                    f"Active dataset schema:\n{schema_text}\n"
                    f"Question: {question}\n"
                    f"Generated SQL: {sql}\n"
                    f"Execution or Validation Error: {err}\n"
                    f"Please fix the SQL query to resolve this error. Return JSON with status and sql."
                )
                try:
                    fix_response = ask_json(system, repair_prompt, demo_mode=simulated)
                except Exception as repair_error:
                    return AgentResult(
                        type="error",
                        sql=sql,
                        message=f"SQL repair generation failed after this error: {err}. {repair_error}",
                        assumptions=plan.get("assumptions", []),
                        simulated=simulated,
                    )
                replacement_sql = fix_response.get("sql")
                if fix_response.get("status") != "ok" or not isinstance(replacement_sql, str) or not replacement_sql.strip():
                    return AgentResult(
                        type="error",
                        sql=sql,
                        message="SQL repair did not return a new query for the active dataset.",
                        assumptions=plan.get("assumptions", []),
                        simulated=simulated,
                    )
                sql = replacement_sql
    else:
        return AgentResult(
            type="error",
            sql=sql,
            message=f"Could not produce a valid query after {retries} retries. Last error: {err}",
            assumptions=plan.get("assumptions", []),
            simulated=simulated,
        )

    query_id = res.get("query_id", "N/A")
    columns = res.get("columns", [])
    rows = res.get("rows", [])

    if not rows:
        return AgentResult(
            type="empty",
            sql=safe_sql,
            query_id=query_id,
            columns=columns,
            rows=[],
            message=(
                "The query executed successfully but returned no matching records. Try broader filters."
                if simulated
                else "The query executed successfully in Snowflake, but returned no matching records. Try broader filters."
            ),
            assumptions=plan.get("assumptions", []),
            simulated=simulated,
        )

    # Explanation synthesis with Gemma
    sample_rows = rows[:50]
    explain_prompt = (
        f"Question: {question}\n"
        f"Columns: {columns}\n"
        f"Rows: {sample_rows}"
    )

    try:
        exp_out = ask_json(EXPLAIN_SYSTEM, explain_prompt, demo_mode=simulated)
        answer_text = exp_out.get("answer", "Analysis completed based on the retrieved data.")
        how_text = exp_out.get("how", "Retrieved and aggregated matching records from Snowflake.")
    except Exception:
        answer_text = (
            "Simulation rows are available; no database data was retrieved."
            if simulated
            else f"Retrieved {len(rows)} record(s) matching your criteria."
        )
        how_text = (
            "Displayed placeholder rows; no database query was executed."
            if simulated
            else f"Executed SQL query against {cfg.database}.{cfg.schema_}."
        )

    grounded = numbers_grounded(answer_text, rows)

    return AgentResult(
        type="ok",
        answer=answer_text,
        how=how_text,
        assumptions=plan.get("assumptions", []),
        sql=safe_sql,
        query_id=query_id,
        columns=columns,
        rows=rows,
        grounded=grounded,
        simulated=simulated,
    )
