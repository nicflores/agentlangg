import json
import os

from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langchain_ollama import ChatOllama

load_dotenv()

from harness.nodes import ResearchNodes
from harness.state import AgentState
from harness.tools import fetch_financials, finish, read_file, web_search, write_file
from harness.trajectory import TrajectoryLogger
from langchain_core.messages import HumanMessage

TOOLS = [web_search, fetch_financials, write_file, read_file, finish]
TOOL_MAP = {t.name: t for t in TOOLS}


def build_graph(ticker: str, price: float, logger: TrajectoryLogger):
    llm = ChatOllama(model="qwen2.5:3b").bind_tools(TOOLS)
    nodes = ResearchNodes(
        ticker=ticker,
        price=price,
        llm=llm,
        tool_map=TOOL_MAP,
        logger=logger,
    )

    graph = StateGraph(AgentState)
    graph.add_node("model", nodes.call_model)
    graph.add_node("tools", nodes.call_tools)
    graph.add_node("nudge", nodes.nudge_model)
    graph.set_entry_point("model")
    graph.add_conditional_edges(
        "model",
        nodes.should_continue,
        {"tools": "tools", "nudge": "nudge", END: END, "model": "model"},
    )
    graph.add_edge("nudge", "model")
    graph.add_edge("tools", "model")

    # Checkpointer: persists state so interrupted runs can be resumed
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


def run(ticker: str, price: float):
    for d in ("workspace", "reports", "trajectories"):
        os.makedirs(d, exist_ok=True)

    logger = TrajectoryLogger(ticker)
    agent = build_graph(ticker, price, logger)

    initial_state: AgentState = {
        "messages": [
            HumanMessage(
                content=f"Research this stock: {json.dumps({'ticker': ticker, 'price': price})}"
            )
        ],
        "ticker": ticker,
        "price": price,
        "done": False,
        "report_path": None,
        "step_count": 0,
        "nudge_count": 0,
        "sources_gathered": [],
        "errors": [],
    }

    # Thread ID enables checkpointer to save/resume this specific run
    config = {"configurable": {"thread_id": ticker}, "recursion_limit": 40}
    final_state = agent.invoke(initial_state, config=config)

    if final_state["report_path"]:
        print(f"\n✓ Report:   {final_state['report_path']}")
        print(f"  Steps:    {final_state['step_count']}")
        print(f"  Nudges:   {final_state['nudge_count']}")
        print(f"  Sources:  {len(final_state['sources_gathered'])}")
        if final_state["errors"]:
            print(f"  Errors:   {final_state['errors']}")
    else:
        print("\n⚠ Agent stopped without calling finish()")
        print(f"  Steps:  {final_state['step_count']}")
        print(f"  Errors: {final_state['errors']}")


if __name__ == "__main__":
    run("AAPL", 182.50)