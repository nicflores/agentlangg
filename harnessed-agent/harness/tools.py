import json
import os

from langchain_core.tools import tool

WORKSPACE = "./workspace"
REPORTS = "./reports"


@tool
def web_search(query: str) -> str:
    """Search the web for current information. Use for news, sentiment, and recent events."""
    from tavily import TavilyClient
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    results = client.search(query, max_results=5)
    return json.dumps(results["results"], indent=2)


@tool
def fetch_financials(ticker: str) -> str:
    """Fetch fundamental financial data for a ticker: P/E, revenue, earnings, market cap."""
    import yfinance as yf
    info = yf.Ticker(ticker).info
    fields = [
        "marketCap", "trailingPE", "forwardPE", "totalRevenue",
        "grossProfits", "earningsGrowth", "revenueGrowth",
        "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "fiftyDayAverage",
        "twoHundredDayAverage", "shortRatio",
    ]
    return json.dumps({k: info.get(k) for k in fields}, indent=2)


@tool
def write_file(filepath: str, content: str) -> str:
    """Write content to a file. Use workspace/ for scratch notes and reports/ for the final report."""
    if filepath.startswith("reports/") or filepath.startswith("./reports/"):
        full_path = filepath.lstrip("./")
    else:
        full_path = os.path.join(WORKSPACE, filepath)

    os.makedirs(os.path.dirname(os.path.abspath(full_path)), exist_ok=True)
    with open(full_path, "w") as f:
        f.write(content)
    return f"Written {len(content)} chars to {full_path}"


@tool
def read_file(filepath: str) -> str:
    """Read a file from the workspace."""
    if filepath.startswith("reports/") or filepath.startswith("./reports/"):
        full_path = filepath.lstrip("./")
    else:
        full_path = os.path.join(WORKSPACE, filepath)

    with open(full_path) as f:
        return f.read()


@tool
def finish(filepath: str) -> str:
    """
    Call this when the final report has been written and the task is complete.
    Pass the filepath of the written report.
    """
    return f"DONE:{filepath}"