# orchestrator/graph.py — northstar-bank
# AgentState schema + compiled LangGraph ReAct agent.

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import tools_condition

from app.orchestrator.state import AgentState
from app.orchestrator.nodes import agent_node, rephraser_node, after_tools_routing
from app.orchestrator.tools import TOOL_NODE

_graph = None


def get_graph():
    """Return the singleton compiled agent graph."""
    global _graph
    if _graph is None:
        builder = StateGraph(AgentState)
        builder.add_node(
            "agent", agent_node
        )  ## The main agent node, which invokes the LLM and emits tool calls or a final answer.
        builder.add_node(
            "tools", TOOL_NODE
        )  ## The tools node which executes the tool calls routed by the agent and updates the state with results.
        builder.add_node(
            "rephraser", rephraser_node
        )  ## Only invoked if RAG returns no results.

        builder.add_edge(START, "agent")

        # After rephrasing, go back to the agent to retry the RAG search with the new question.
        builder.add_edge("rephraser", "agent")

        # If the agent emits a tool call, go to the tools node; else end.
        builder.add_conditional_edges("agent", tools_condition)
        builder.add_conditional_edges(
            "tools", after_tools_routing, {"rephraser": "rephraser", "agent": "agent"}
        )

        _graph = builder.compile()

        # Generate and save the graph visualisation
        graph_image = _graph.get_graph().draw_mermaid_png()
        with open("app/flow.png", "wb") as f:
            f.write(graph_image)

    return _graph
