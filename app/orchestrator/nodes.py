# orchestrator/nodes.py — northstar-bank

from langchain_core.messages import HumanMessage, SystemMessage
from app.utils.prompts import AGENT_SYSTEM_PROMPT, REPHRASER_SYSTEM_PROMPT
from app.orchestrator.state import AgentState
from app.orchestrator.tools import TOOLS
from app.utils.openai_client import get_chat_llm
from config import MAX_RETRY, REPHRASER_TEMPERATURE


def agent_node(state: AgentState) -> AgentState:
    """Invoke the LLM. Emits tool calls or a final answer."""
    llm = get_chat_llm().bind_tools(TOOLS)
    response = llm.invoke([SystemMessage(content=AGENT_SYSTEM_PROMPT)] + state["messages"])
    updates: AgentState = {"messages": [response]}
    if not response.tool_calls:
        updates["intent"] = state["intent"] or "chat"
    return updates


def rephraser_node(state: AgentState) -> AgentState:
    """Rephrase the question and inject a retry instruction."""
    original = state["original_question"] or state["question"]
    response = get_chat_llm(temperature=REPHRASER_TEMPERATURE).invoke([
        SystemMessage(content=REPHRASER_SYSTEM_PROMPT),
        HumanMessage(content=original),
    ])
    rephrased = response.content.strip()
    return {
        "question":    rephrased,
        "retry_count": state["retry_count"] + 1,
        "sources":     [],
        "messages": [HumanMessage(content=(
            f"The previous search returned no relevant results. "
            f"Please search the knowledge base again using this "
            f"rephrased question: {rephrased}"
        ))],
    }


def after_tools_routing(state: AgentState) -> str:
    """Rephrase and retry if RAG returned nothing and budget remains, else back to agent."""
    rag_empty = state["intent"] == "rag" and not state["sources"]
    if rag_empty and state["retry_count"] < MAX_RETRY:
        return "rephraser"
    return "agent"
