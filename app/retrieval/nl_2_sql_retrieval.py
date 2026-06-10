# app/retrieval/nl_2_sql_retrieval.py — northstar-bank
# NL-to-SQL pipeline: question → SQL generation → validated execution.

import re

from langchain_community.utilities import SQLDatabase
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from app.utils.db import get_readonly_connection
from app.utils.openai_client import get_chat_llm
from app.utils.prompts import NL_TO_SQL_GENERATOR_PROMPT
from config import AGENTIC_URL

# ── SQL generation ────────────────────────────────────────────────────────────

_BANKING_TABLES = [
    "accounts",
    "transactions",
    "loan_accounts",
    "fixed_deposits",
    "credit_cards",
    "card_transactions",
]


_db: SQLDatabase | None = None


def _get_db() -> SQLDatabase:
    global _db
    if _db is None:
        # SQLAlchemy requires the psycopg2 dialect prefix; psycopg2.connect() does not.
        sa_url = AGENTIC_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
        _db = SQLDatabase.from_uri(
            sa_url,
            include_tables=_BANKING_TABLES,
        )
    return _db


def generate_sql(question: str) -> str:
    llm = get_chat_llm(temperature=0)
    schema = _get_db().get_table_info()

    prompt = ChatPromptTemplate.from_messages([
        ("system", NL_TO_SQL_GENERATOR_PROMPT),
        ("human", "Schema:\n{schema}\n\nQuestion:\n{question}")
    ])

    chain = prompt | llm | StrOutputParser()
    raw_sql = chain.invoke({
        "schema": schema,
        "question": question
    })

    raw_sql = raw_sql.strip()
    raw_sql = re.sub(r"^```sql\s*", "", raw_sql, flags=re.IGNORECASE)
    raw_sql = re.sub(r"^```\s*", "", raw_sql)
    raw_sql = re.sub(r"\s*```$", "", raw_sql)

    return raw_sql.strip()



# ── SQL execution ─────────────────────────────────────────────────────────────

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|CREATE|ALTER|GRANT|REVOKE|EXECUTE|EXEC|COPY)\b",
    re.IGNORECASE,
)
_MAX_ROWS = 50


def execute_sql(sql: str) -> dict:
    """Validate and execute a SELECT query; return columns + rows."""
    if _FORBIDDEN.search(sql):
        raise ValueError("Query contains a forbidden keyword.")

    conn = get_readonly_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchmany(_MAX_ROWS)
            columns = (
                [col_desc[0] for col_desc in cur.description] if cur.description else []
            )
    finally:
        conn.close()

    return {"query": sql, "columns": columns, "rows": [list(row) for row in rows]}
