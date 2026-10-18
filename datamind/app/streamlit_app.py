"""DataMind: Talk to your data.
Streamlit Conversational Data Application powered by Snowflake and Google Gemma.
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv

from datamind.config import load_config
from datamind.snowflake_client import SnowflakeClient
from datamind.schema import build_schema_text
from datamind.agent import answer
from datamind.conversation import reset_dataset_conversation

load_dotenv()

st.set_page_config(
    page_title="DataMind - Talk to Your Data",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .metric-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .badge-success { background-color: #DEF7EC; color: #03543F; }
    .badge-warning { background-color: #FEF08A; color: #713F12; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Sidebar Configuration
st.sidebar.image("https://img.icons8.com/fluency/96/artificial-intelligence.png", width=64)
st.sidebar.title("DataMind Control")

dataset_options = {
    "TPC-H SF1 (Snowflake Sample Benchmark)": "configs/tpch.yaml",
    "Our World in Data (Energy & Climate)": "configs/owid.yaml",
}

selected_label = st.sidebar.selectbox("Select Active Dataset", list(dataset_options.keys()))
cfg_path = dataset_options[selected_label]

# Conversation context and displayed answers belong to one dataset only.
reset_dataset_conversation(st.session_state, cfg_path)

# Load Configuration and Initialize Snowflake
try:
    cfg = load_config(cfg_path)
    sf = SnowflakeClient(database=cfg.database, schema=cfg.schema_)
    schema_text = build_schema_text(cfg, sf)
except Exception as e:
    st.sidebar.error(f"Initialization failed: {e}")
    st.stop()

# System Status in Sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("System Architecture")
st.sidebar.markdown(f"**Data Platform:** Snowflake (`{cfg.database}.{cfg.schema_}`)")
st.sidebar.markdown(f"**LLM Generator:** Gemma (`{os.environ.get('OLLAMA_MODEL', 'gemma3n:e4b')}`)")
st.sidebar.markdown(f"**Guardrails:** `sqlglot` AST Validation")

if sf.demo_mode:
    st.sidebar.warning(
        f"Simulation/Demo Mode: {sf.demo_reason}. Results are simulated, not retrieved from Snowflake."
    )
else:
    st.sidebar.success(" Connected to Snowflake Live")

# Sample questions by dataset
st.sidebar.markdown("---")
st.sidebar.subheader("💡 Example Questions")

sample_questions = {
    "configs/tpch.yaml": [
        "How many total orders are in the database?",
        "What are the top 5 nations by customer count?",
        "Show total revenue broken down by order priority",
        "Which market segments have the highest account balances?",
    ],
    "configs/owid.yaml": [
        "Which countries have the highest renewables share in 2022?",
        "Compare CO2 emissions between United States and China over time",
        "What is the total energy consumption per country in 2021?",
        "Which nations had more than 50% renewable energy?",
    ],
}

active_samples = sample_questions.get(cfg_path, [])
for sq in active_samples:
    if st.sidebar.button(sq, key=f"sq_{sq}"):
        st.session_state["prompt_input"] = sq

# Main UI Area
st.markdown('<div class="main-header">🧠 DataMind: Talk to Your Data</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Data-grounded conversational analytics with Google Gemma, Snowflake, and verifiable AST guardrails.</div>',
    unsafe_allow_html=True,
)

# Chat input
default_prompt = st.session_state.pop("prompt_input", "")
user_query = st.chat_input("Ask any business or analytics question about this dataset...")
if default_prompt and not user_query:
    user_query = default_prompt

if user_query:
    with st.spinner("Analyzing question, generating Snowflake SQL with Gemma, and validating guardrails..."):
        res = answer(user_query, cfg, sf, schema_text, st.session_state.history)

    st.session_state.history.append(f"User: {user_query}")
    if res.get("answer"):
        st.session_state.history.append(f"Agent: {res['answer']}")

    st.session_state.responses.insert(
        0,
        {"query": user_query, "result": res, "dataset": selected_label},
    )

# Display conversation responses (latest on top)
if st.session_state.responses:
    for idx, item in enumerate(st.session_state.responses):
        q = item["query"]
        res = item["result"]

        st.caption(
            f"Dataset: {item['dataset']} · "
            f"{'SIMULATED — not queried from Snowflake' if res.get('simulated') else 'Snowflake result'}"
        )
        st.markdown(f"### 💬 Question: *\"{q}\"*")

        res_type = res.get("type")

        if res_type == "clarify":
            st.info(f"🤔 **Clarification Needed:** {res.get('message')}")
            if res.get("assumptions"):
                st.caption(f"Context: {', '.join(res['assumptions'])}")

        elif res_type == "unsupported":
            st.warning(f"🚫 **Request Unsupported:** {res.get('message')}")

        elif res_type == "empty":
            st.warning(f"🔍 **No Matching Records:** {res.get('message')}")
            with st.expander("Inspect Executed SQL Query"):
                st.code(res.get("sql", ""), language="sql")
                query_id_label = "Simulation ID" if res.get("simulated") else "Snowflake Query ID"
                st.caption(f"{query_id_label}: `{res.get('query_id')}`")

        elif res_type == "error":
            st.error(f"❌ **Error Encountered:** {res.get('message')}")
            if res.get("sql"):
                with st.expander("Attempted SQL"):
                    st.code(res["sql"], language="sql")

        elif res_type == "ok":
            # Successful grounded response
            tabs = st.tabs([
                "📌 Answer & Insights",
                "🔍 How I Got This",
                "⚡ SQL & Evidence",
                "📊 Result Rows",
                "📈 Visualizations",
            ])

            # Tab 1: Answer
            with tabs[0]:
                st.markdown(f"#### {res.get('answer')}")

                if res.get("simulated"):
                    st.warning(
                        "Simulation only: these rows were not retrieved from Snowflake. "
                        "Any numeric matching is not evidence about the real dataset."
                    )
                elif res.get("grounded", True):
                    st.success("✅ **Grounding Verified:** All numeric facts in this answer were checked against Snowflake rows.")
                else:
                    st.warning("⚠️ **Grounding Warning:** Some numbers in the generated summary could not be strictly matched against retrieved rows.")

                # Assumptions
                if res.get("assumptions"):
                    with st.expander("View Assumptions Made"):
                        for a in res["assumptions"]:
                            st.markdown(f"- {a}")

            # Tab 2: How I Got This
            with tabs[1]:
                st.markdown("#### Methodology & Plain-Language Steps")
                st.write(res.get("how", "No explanation provided."))

                st.markdown("#### Schema Traceability")
                st.markdown(f"- **Target Database:** `{cfg.database}`")
                st.markdown(f"- **Target Schema:** `{cfg.schema_}`")
                st.markdown(f"- **Max Allowed Rows:** `{cfg.max_rows}`")

            # Tab 3: SQL & Evidence
            with tabs[2]:
                st.markdown("#### Executed Snowflake SQL (Read-Only Guardrailed)")
                st.code(res.get("sql", ""), language="sql")

                c1, c2 = st.columns(2)
                with c1:
                    st.metric(
                        "Simulation ID" if res.get("simulated") else "Snowflake Query ID",
                        res.get("query_id", "N/A"),
                    )
                with c2:
                    st.metric("Rows Retrieved", len(res.get("rows", [])))

            # Tab 4: Result Rows
            with tabs[3]:
                rows = res.get("rows", [])
                cols = res.get("columns", [])
                if rows and cols:
                    df = pd.DataFrame(rows, columns=cols)
                    st.dataframe(df, use_container_width=True)

                    csv = df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        label="📥 Download Data as CSV",
                        data=csv,
                        file_name=f"datamind_export_{idx}.csv",
                        mime="text/csv",
                    )
                else:
                    st.info("No tabular data to display.")

            # Tab 5: Visualizations
            with tabs[4]:
                rows = res.get("rows", [])
                cols = res.get("columns", [])
                if rows and cols and len(rows) > 0:
                    df = pd.DataFrame(rows, columns=cols)
                    num_cols = df.select_dtypes(include=["number"]).columns.tolist()
                    cat_cols = df.select_dtypes(include=["object", "string", "category"]).columns.tolist()

                    if num_cols and cat_cols:
                        st.markdown("#### Interactive Plotly Chart")
                        x_col = st.selectbox("X-Axis (Category/Dimension)", cat_cols, key=f"x_{idx}")
                        y_col = st.selectbox("Y-Axis (Metric)", num_cols, key=f"y_{idx}")

                        chart_type = st.radio("Chart Type", ["Bar Chart", "Line Chart"], horizontal=True, key=f"ct_{idx}")
                        if chart_type == "Bar Chart":
                            fig = px.bar(df, x=x_col, y=y_col, title=f"{y_col} by {x_col}", template="plotly_white")
                        else:
                            fig = px.line(df, x=x_col, y=y_col, title=f"{y_col} by {x_col}", markers=True, template="plotly_white")
                        st.plotly_chart(fig, use_container_width=True)
                    elif len(num_cols) >= 2:
                        st.markdown("#### Metric Correlation")
                        fig = px.scatter(df, x=num_cols[0], y=num_cols[1], title=f"{num_cols[1]} vs {num_cols[0]}", template="plotly_white")
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("Results table has single dimension. View data in the Rows tab.")
                else:
                    st.info("No data available for plotting.")

        st.markdown("---")
else:
    # Welcome hero
    st.info("👋 Welcome to **DataMind**! Type a question below or choose an example from the sidebar to explore your Snowflake data in natural language.")
