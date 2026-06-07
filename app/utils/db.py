# app/utils/db.py — northstar-bank
# Plain psycopg2 connection helper. One connection per call, closed by the caller.

import psycopg2
from config import DATABASE_URL, AGENTIC_URL


def get_connection() -> psycopg2.extensions.connection:
    """Open and return a new Postgres connection. Caller must call conn.close()."""
    return psycopg2.connect(DATABASE_URL)


def get_readonly_connection() -> psycopg2.extensions.connection:
    """Open and return a read-only Postgres connection. Caller must call conn.close()."""
    return psycopg2.connect(AGENTIC_URL)
