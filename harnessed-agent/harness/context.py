MAX_TOOL_OUTPUT_CHARS = 3200  # ~800 tokens


def truncate_tool_output(output: str, max_chars: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    """
    Keep the head and tail of large tool outputs.
    Mirrors the LangChain harness pattern: keep enough for the model to understand
    what it received without blowing out the context window.
    """
    if len(output) <= max_chars:
        return output

    head = output[:max_chars // 2]
    tail = output[-(max_chars // 4):]
    trimmed = len(output) - len(head) - len(tail)

    return (
        f"{head}\n"
        f"\n... [{trimmed} chars truncated — full output saved to workspace if needed] ...\n\n"
        f"{tail}"
    )


def wrap_tool_result(tool_name: str, raw_output: str) -> str:
    """Apply compaction and label the result clearly."""
    compacted = truncate_tool_output(raw_output)
    return f"[{tool_name} result]\n{compacted}"