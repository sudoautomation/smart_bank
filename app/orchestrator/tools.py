# orchestrator/tools.py — northstar-bank
# LangGraph @tool definitions used by the ReAct agent.

from typing import Annotated
from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import ToolNode
from app.retrieval.nl_2_sql_retrieval import execute_sql, generate_sql
from app.retrieval.multimodal_retrieval import retrieve
from app.orchestrator.state import AgentState


@tool
def rag_retrieval(
    query: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> AgentState:
    """Search the banking knowledge base for general product information, policies, procedures, fees, eligibility, and terms. Use for 'how does X work', 'what are the rules', 'eligibility for', 'documentation needed' type questions."""
    chunks = retrieve(query)
    if not chunks:
        return {
            "sources": [],
            "intent": "rag",
            "messages": [
                ToolMessage(
                    content="No relevant information found in the knowledge base for this query.",
                    tool_call_id=tool_call_id,
                )
            ],
        }
    content = "\n\n---\n\n".join(
        f"[Source: {chunk['source_file']} | "
        f"Section: {chunk['section'] or 'N/A'} | "
        f"Page: {chunk['page_number'] or 'N/A'}]\n{chunk['content']}"
        for chunk in chunks
    )
    sources = [
        {
            "source": chunk["source_file"],
            "score": float(chunk["score"]),
            "section": chunk["section"],
            "page_number": chunk["page_number"],
        }
        for chunk in chunks
    ]
    return {
        "sources": sources,
        "intent": "rag",
        "messages": [ToolMessage(content=content, tool_call_id=tool_call_id)],
    }


@tool
def nl_to_sql_query(
    question: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> AgentState:
    """Query the live banking database for specific record-level or real-time data: 
    account balances, transactions, active loans, fixed deposits (FDs) for a customer/account, credit card details, EMI schedules, 
    or any question referencing a specific account ID or customer."""
    try:
        sql = generate_sql(question)
        result = execute_sql(sql)
    except Exception as exc:
        result = {"query": None, "columns": [], "rows": [], "error": str(exc)}

    if result.get("error"):
        content = f"Database query failed: {result['error']}"
    else:
        columns = result["columns"]
        rows = result["rows"]
        rows_preview = "\n".join(str(dict(zip(columns, row))) for row in rows[:20])
        content = f"{len(rows)} row(s) returned\n{rows_preview}"

    return {
        "sql_result": result,
        "intent": "nl_to_sql",
        "messages": [ToolMessage(content=content, tool_call_id=tool_call_id)],
    }


TOOLS = [rag_retrieval, nl_to_sql_query]
TOOL_NODE = ToolNode(TOOLS)