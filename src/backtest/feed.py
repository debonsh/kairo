"""Backtrader-compatible data feed from DuckDB."""
import duckdb
import pandas as pd
from datetime import datetime
import backtrader as bt


class DuckDBData(bt.feeds.PandasData):
    params = (
        ("datetime", None),
        ("open", "open"),
        ("high", "high"),
        ("low", "low"),
        ("close", "close"),
        ("volume", "volume"),
        ("openinterest", None),
    )


def load_dataframe(store, exchange: str, symbol: str, timeframe: str,
                   start_dt: datetime | None = None, end_dt: datetime | None = None) -> pd.DataFrame:
    records = store.get_candles(exchange, symbol, timeframe,
                                start_dt.timestamp() * 1000 if start_dt else None,
                                end_dt.timestamp() * 1000 if end_dt else None)
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.set_index("datetime")
    df.columns = [c.lower() for c in df.columns]
    required = ["open", "high", "low", "close", "volume"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")
    return df


def create_feed(df: pd.DataFrame) -> DuckDBData:
    return DuckDBData(dataname=df)
