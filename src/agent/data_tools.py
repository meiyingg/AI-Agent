"""外部实时数据工具:Yahoo Finance 行情(免费、无需 API key)。

返回**真实**股价/ETF/指数数据(非模型记忆里的旧数据),并附上每日收盘价序列——
模型可以接着用 run_python 在这组真数据上算收益率/波动率等,组成"取真数据 + 写代码分析"的闭环。
"""
from langchain_core.tools import tool


@tool(description="Fetch REAL market data for a stock / ETF / index from Yahoo Finance (free, live, no API key). "
                  "Use this for current or recent prices instead of relying on memory. "
                  "Args: ticker (symbol, e.g. AAPL, MSFT, NVDA, ^GSPC for S&P 500, D05.SI for DBS in Singapore); "
                  "period (one of 1d,5d,1mo,3mo,6mo,1y,2y,5y,max — default 1mo). "
                  "Returns the last price, change over the period, high/low, and the daily closing prices "
                  "(so you can compute returns/volatility with run_python).")
def get_stock_data(ticker: str, period: str = "1mo") -> str:
    import yfinance as yf

    sym = str(ticker).strip().upper()
    valid = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"}
    period = str(period).strip().lower()
    if period not in valid:
        period = "1mo"
    try:
        t = yf.Ticker(sym)
        hist = t.history(period=period, auto_adjust=True)
    except Exception as e:
        return f"[error] Could not fetch '{sym}' from Yahoo Finance: {e}"
    if hist is None or hist.empty or "Close" not in hist:
        return (f"[error] No data for '{sym}'. Check the symbol "
                "(e.g. AAPL, MSFT, ^GSPC for S&P 500, D05.SI for DBS).")

    closes = hist["Close"].dropna()
    if closes.empty:
        return f"[error] No closing prices returned for '{sym}'."
    last, first = float(closes.iloc[-1]), float(closes.iloc[0])
    chg = (last / first - 1) * 100 if first else 0.0
    hi, lo = float(closes.max()), float(closes.min())

    cur = ""
    try:                                   # currency 尽力而为,拿不到不影响主结果
        fi = t.fast_info
        cur = (fi.get("currency") if isinstance(fi, dict) else getattr(fi, "currency", "")) or ""
    except Exception:
        pass

    vals = [round(float(c), 2) for c in closes.tolist()][-260:]   # 最多 ~1 年,防过长
    series = ", ".join(f"{v:.2f}" for v in vals)
    return (f"{sym} - Yahoo Finance, period={period} ({len(closes)} trading days)\n"
            f"  last close: {last:.2f} {cur}\n"
            f"  change over period: {chg:+.2f}%   (high {hi:.2f}, low {lo:.2f})\n"
            f"  daily closes: [{series}]")
