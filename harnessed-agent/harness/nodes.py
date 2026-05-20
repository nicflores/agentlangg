import os

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from harness.context import wrap_tool_result
from harness.prompts import NUDGE_TEMPLATE, SYSTEM_PROMPT
from harness.state import AgentState
from harness.tools import REPORTS
from harness.trajectory import TrajectoryLogger


class ResearchNodes:
    """
    Encapsulates all LangGraph node functions for the research agent.
    Dependencies (llm, ticker, logger) are injected explicitly rather
    than captured via closure, making each node independently testable.
    """

    def __init__(self, ticker: str, price: float, llm, tool_map: dict, logger: TrajectoryLogger):
        self.ticker = ticker
        self.price = price
        self.llm = llm
        self.tool_map = tool_map
        self.logger = logger

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    def call_model(self, state: AgentState) -> AgentState:
        messages = state["messages"]

        # Inject system prompt on first call only
        if not any(isinstance(m, SystemMessage) for m in messages):
            system = SystemMessage(
                content=SYSTEM_PROMPT.format(ticker=self.ticker)
            )
            messages = [system] + messages

        self.logger.log("model_call", {
            "step_count": state["step_count"],
            "message_count": len(messages),
        })

        response = self.llm.invoke(messages)

        self.logger.log("model_response", {
            "content": response.content[:200],
            "tool_calls": [tc["name"] for tc in (response.tool_calls or [])],
        })

        return {
            **state,
            "messages": [response],
            "step_count": state["step_count"] + 1,
        }

    def call_tools(self, state: AgentState) -> AgentState:
        last = state["messages"][-1]
        results = []
        done = state["done"]
        report_path = state["report_path"]
        sources = list(state["sources_gathered"])
        errors = list(state["errors"])

        for tc in last.tool_calls:
            self.logger.log("tool_call", {
                "tool": tc["name"],
                "args": tc["args"],
                "step_count": state["step_count"],
            })

            # Execute with error handling — model can recover from a
            # reported failure; it cannot recover from an exception
            try:
                raw = self.tool_map[tc["name"]].invoke(tc["args"])
            except Exception as e:
                error_msg = f"ERROR: {tc['name']} failed — {e}. Try a different approach."
                self.logger.log("tool_error", {
                    "tool": tc["name"],
                    "error": str(e),
                })
                errors.append(f"{tc['name']}: {e}")
                results.append(ToolMessage(content=error_msg, tool_call_id=tc["id"]))
                continue

            # Completion hook — verify the file exists before accepting finish()
            if isinstance(raw, str) and raw.startswith("DONE:"):
                candidate_path = raw[5:]
                full_path = os.path.join(REPORTS, os.path.basename(candidate_path))

                if os.path.exists(candidate_path) or os.path.exists(full_path):
                    done = True
                    report_path = candidate_path
                    result_content = f"Report verified at {candidate_path}. Task complete."
                    self.logger.log("finish_accepted", {"path": candidate_path})
                else:
                    result_content = (
                        f"ERROR: finish() called but no file found at {candidate_path}. "
                        f"You must call write_file first to write the complete report "
                        f"content, then call finish() again."
                    )
                    self.logger.log("finish_rejected", {
                        "path": candidate_path,
                        "reason": "file_not_found",
                    })
            else:
                # Track which tools have been used as sources
                if tc["name"] in ("web_search", "fetch_financials"):
                    sources.append(tc["name"])

                result_content = wrap_tool_result(tc["name"], str(raw))

            self.logger.log("tool_result", {
                "tool": tc["name"],
                "truncated_len": len(result_content),
            })
            results.append(ToolMessage(content=result_content, tool_call_id=tc["id"]))

        return {
            **state,
            "messages": results,
            "done": done,
            "report_path": report_path,
            "sources_gathered": sources,
            "errors": errors,
        }

    def nudge_model(self, state: AgentState) -> AgentState:
        nudge_count = state["nudge_count"] + 1
        self.logger.log("nudge", {
            "nudge_count": nudge_count,
            "step_count": state["step_count"],
        })

        # Use SystemMessage to distinguish harness control from user input
        nudge_msg = SystemMessage(
            content=NUDGE_TEMPLATE.format(ticker=self.ticker)
        )

        return {
            **state,
            "messages": [nudge_msg],
            "nudge_count": nudge_count,
        }

    # ------------------------------------------------------------------
    # Router
    # ------------------------------------------------------------------

    def should_continue(self, state: AgentState) -> str:
        from langgraph.graph import END

        if state["done"]:
            return END

        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"

        # Count consecutive AI responses with no tool calls
        empty_streak = 0
        for m in reversed(state["messages"]):
            is_ai = hasattr(m, "tool_calls")
            if is_ai and not m.tool_calls:
                empty_streak += 1
            else:
                break

        if empty_streak >= 2:
            return "nudge"

        return "model"