from typing import Annotated
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    ticker: str
    price: float
    done: bool
    report_path: str | None
    step_count: int
    nudge_count: int
    sources_gathered: list[str]
    errors: list[str]