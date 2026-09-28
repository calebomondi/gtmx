from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import ToolNode, tools_condition

from agents.tools import scrape_url, parse_document
from agents.llm.main import _llm

# --- State ---
class GatherContextState(TypedDict):
    """
    State for the GatherContext subgraph.
    """
    messages: Annotated[list, add_messages]  # List of messages in the conversation

# --- Tools ---
GATHER_TOOLS = [scrape_url, parse_document]

# -- TODO: LIMIT MESSEAGES TO THE LAST 6

# --- Node ---
def call_gather_model(state: GatherContextState) -> dict:
    """
    Call the LLM to gather context from the user.
    """
    llm = _llm().bind_tools(GATHER_TOOLS)

    if len(state["messages"]) == 1:
        system = SystemMessage(content="""You help gather raw source content
before product information is extracted.

- If the user's message contains a URL, call scrape_url with the URL EXACTLY
  as the user wrote it — verbatim. Do not append paths, do not navigate to
  subpages or sections of the site, and do not remove or truncate any part
  of it. The URL the user shares is the single source of truth.
- If the user references a document/file path, call parse_document on it.
- If there is no URL or file reference, do not call any tool — just
  respond with exactly: "No content to gather."
- After a tool returns content, do not summarize, extract fields, or
  interpret it — just respond with the raw content you received, verbatim,
  so it can be processed downstream. Do not call more than one tool total
  unless the user's message clearly contains more than one URL/file.
""")
        messages = [system] + state["messages"]
    else:
        messages = state["messages"]

    response = llm.invoke(messages)
    return {"messages": [response]}

# -- Graph ---
def gather_context_graph():
    gather_sub = StateGraph(GatherContextState)

    # -- Nodes --
    gather_sub.add_node("call_gather_model", call_gather_model)
    gather_sub.add_node("tools", ToolNode(GATHER_TOOLS))
    # -- Edges --
    gather_sub.add_edge(START, "call_gather_model")
    gather_sub.add_conditional_edges("call_gather_model", tools_condition)
    gather_sub.add_edge("tools", "call_gather_model")

    return gather_sub.compile()