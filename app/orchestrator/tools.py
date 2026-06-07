# orchestrator/tools.py — northstar-bank
# LangGraph @tool definitions used by the ReAct agent.

from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import ToolNode
from langgraph.types import Command

from app.retrieval.nl_2_sql_retrieval import execute_sql, generate_sql
from app.retrieval.multimodal_retrieval import retrieve


@tool
def rag_retrieval(
    query: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Search the BFSI banking knowledge base for policies, products, fees, and procedures."""
    chunks = retrieve(query)

    if not chunks:
        content = "No relevant information found in the knowledge base for this query."
        sources: list[dict] = []
    else:
        content = "\n\n---\n\n".join(
            f"[Source: {chunk['source_file']} | "
            f"Section: {chunk['section'] or 'N/A'} | "
            f"Page: {chunk['page_number'] or 'N/A'}]\n{chunk['content']}"
            for chunk in chunks
        )
        sources = [
            {
                "source":      chunk["source_file"],
                "score":       float(chunk["score"]),
                "section":     chunk["section"],
                "page_number": chunk["page_number"],
            }
            for chunk in chunks
        ]

    return Command(update={
        "sources":  sources,
        "intent":   "rag",
        "messages": [ToolMessage(content=content, tool_call_id=tool_call_id)],
    })


@tool
def nl_to_sql_query(
    question: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Query the live banking database for account, transaction, loan, and customer data."""
    try:
        sql = generate_sql(question)
        print(f"Generated SQL:\n{sql}\n")
        result = execute_sql(sql)
    except Exception as exc:
        result = {"query": None, "columns": [], "rows": [], "error": str(exc)}

    if result.get("error"):
        content = f"Database query failed: {result['error']}"
    else:
        columns = result["columns"]
        rows    = result["rows"]
        rows_preview = "\n".join(str(dict(zip(columns, row))) for row in rows[:20])
        content = (
            f"SQL executed:\n{result['query']}\n\n"
            f"Result: {len(rows)} row(s) returned\n{rows_preview}"
        )

    return Command(update={
        "sql_result": result,
        "intent":     "nl_to_sql",
        "messages":   [ToolMessage(content=content, tool_call_id=tool_call_id)],
    })


TOOLS = [rag_retrieval, nl_to_sql_query]
TOOL_NODE = ToolNode(TOOLS)
