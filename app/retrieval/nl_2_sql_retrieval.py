# app/retrieval/nl_2_sql_retrieval.py — northstar-bank
# NL-to-SQL pipeline: question → SQL generation → validated execution.

import re

from langchain_classic.chains import create_sql_query_chain
from langchain_community.utilities import SQLDatabase

from app.utils.db import get_readonly_connection
from app.utils.openai_client import get_chat_llm
from config import AGENTIC_URL, NL_TO_SQL_TEMPERATURE

# ── SQL generation ────────────────────────────────────────────────────────────

_BANKING_TABLES = [
    "accounts", "transactions", "loan_accounts",
    "fixed_deposits", "credit_cards", "card_transactions",
]
_CLEANUP_RE = re.compile(
    r"^SQLQuery:\s*|```sql\s*|```\s*$", re.IGNORECASE | re.MULTILINE)

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
    """Generate a SELECT SQL query from a natural language question."""
    llm = get_chat_llm(temperature=NL_TO_SQL_TEMPERATURE)
    chain = create_sql_query_chain(llm, _get_db())
    raw = chain.invoke({"question": question})
    return _CLEANUP_RE.sub("", raw).strip()


# ── SQL execution ─────────────────────────────────────────────────────────────

_SELECT_RE = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|CREATE|ALTER|GRANT|REVOKE|EXECUTE|EXEC|COPY)\b",
    re.IGNORECASE,
)
_MAX_ROWS = 50


def execute_sql(sql: str) -> dict:
    """Validate and execute a SELECT query; return columns + rows."""
    if not _SELECT_RE.match(sql):
        raise ValueError("Only SELECT statements are permitted.")
    if _FORBIDDEN.search(sql):
        raise ValueError("Query contains a forbidden keyword.")

    conn = get_readonly_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchmany(_MAX_ROWS)
            columns = [col_desc[0] for col_desc in cur.description] if cur.description else []
    finally:
        conn.close()

    return {"query": sql, "columns": columns, "rows": [list(row) for row in rows]}
