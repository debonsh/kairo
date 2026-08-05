"""Information-driven bars — volume bars, dollar bars, tick bars, CUSUM bars.
Replaces time-based OHLCV sampling with information-arrival sampling.
Crypto trades 24/7 with wildly uneven activity — time bars oversample
dead hours and blur the information-carrying bursts.

ponytail: volume bars + dollar bars for v0, CUSUM filtering for v0.3."""

from collections import deque
from datetime import datetime
import numpy as np
from loguru import logger


class CUSUMBars:
    """CUSUM-filtered bar sampling — structural break detection.

    Instead of static thresholds (volume/dollar/tick), CUSUM watches
    cumulative deviations from a running mean of returns. When cumulative
    sum crosses a threshold, it flushes a bar — capturing the exact moment
    the market regime shifted (vol spike, breakout, crash).

    Reference: De Prado, Advances in Financial Machine Learning, Chapter 2.
    """

    def __init__(self, threshold: float = 0.5, warmup: int = 30):
        self.threshold = threshold
        self.warmup = warmup
        self._returns: deque = deque(maxlen=500)
        self._cusum_pos: float = 0.0
        self._cusum_neg: float = 0.0
        self._mean: float = 0.0
        self._std: float = 0.01
        self._prev_close: float = 0.0

        self._open: float | None = None
        self._high: float = -float("inf")
        self._low: float = float("inf")
        self._close: float | None = None
        self._volume: float = 0.0
        self._timestamp: int | None = None
        self._symbol: str = ""
        self._sample_count: int = 0

    def _update_stats(self):
        if len(self._returns) < self.warmup:
            return
        arr = np.array(list(self._returns), dtype=float)
        self._mean = float(np.mean(arr))
        self._std = max(float(np.std(arr)), 0.0001)

    def add_tick(self, price: float, volume: float, timestamp: int, symbol: str = "") -> dict | None:
        if self._open is None:
            self._open = price
            self._timestamp = timestamp
            self._symbol = symbol
            self._prev_close = price
            self._returns.append(0.0)
        else:
            ret = (price - self._prev_close) / self._prev_close if self._prev_close > 0 else 0.0
            self._returns.append(float(ret))
            self._prev_close = price

        self._high = max(self._high, price)
        self._low = min(self._low, price)
        self._close = price
        self._volume += volume
        self._sample_count += 1

        self._update_stats()

        if len(self._returns) < self.warmup:
            return None

        latest = self._returns[-1]
        if self._std == 0:
            return None
        z = (latest - self._mean) / self._std

        drift = 0.005
        self._cusum_pos = max(0, self._cusum_pos + z - drift)
        self._cusum_neg = min(0, self._cusum_neg + z + drift)

        if max(self._cusum_pos, abs(self._cusum_neg)) >= self.threshold:
            bar = self._flush()
            self._cusum_pos = 0.0
            self._cusum_neg = 0.0
            return bar

        return None

    def _flush(self) -> dict | None:
        if self._open is None:
            return None
        bar = {
            "symbol": self._symbol,
            "timestamp": self._timestamp,
            "open": self._open,
            "high": self._high,
            "low": self._low,
            "close": self._close,
            "base_volume": self._volume,
            "trades": self._sample_count,
            "bar_type": "cusum",
        }
        self._open = None
        self._high = -float("inf")
        self._low = float("inf")
        self._close = None
        self._volume = 0.0
        self._sample_count = 0
        return bar


def candles_to_cusum_bars(candles: list, threshold: float = 0.5, warmup: int = 30) -> list[list]:
    """Convert time-based OHLCV candles into CUSUM-driven bars.

    Returns bars in standard ccxt [[ts, o, h, l, c, v], ...] format.
    """
    if not candles:
        return []
    bars = CUSUMBars(threshold=threshold, warmup=warmup)
    result = []
    for candle in candles:
        if not isinstance(candle, (list, tuple)) or len(candle) < 6:
            continue
        ts, o, h, l, c, v = candle[0], candle[1], candle[2], candle[3], candle[4], candle[5]
        bar = bars.add_tick(price=c, volume=v, timestamp=int(ts))
        if bar:
            result.append([int(bar["timestamp"]), bar["open"], bar["high"], bar["low"], bar["close"], bar["base_volume"]])
    last = bars._flush()
    if last and last["base_volume"] > 0 and last["close"] is not None:
        result.append([int(last["timestamp"]), last["open"], last["high"], last["low"], last["close"], last["base_volume"]])
    return result


class InformationBars:
    def __init__(self, bar_type: str = "volume", threshold: float | None = None):
        self.bar_type = bar_type
        self.threshold = threshold
        self.ticks: deque = deque()
        self.cumulative_volume = 0.0
        self.cumulative_dollar = 0.0
        self.tick_count = 0

        self._open = None
        self._high = -float("inf")
        self._low = float("inf")
        self._close = None
        self._base_volume = 0.0
        self._quote_volume = 0.0
        self._timestamp = None
        self._symbol = ""

    def add_tick(self, price: float, volume: float, timestamp: int, symbol: str = "") -> dict | None:
        if self._open is None:
            self._open = price
            self._timestamp = timestamp
            self._symbol = symbol

        self._high = max(self._high, price)
        self._low = min(self._low, price)
        self._close = price
        self._base_volume += volume
        self._quote_volume += price * volume
        self.tick_count += 1

        self.cumulative_volume += volume
        self.cumulative_dollar += price * volume

        if self._should_flush() and self._open is not None:
            bar = self._flush()
            return bar

        return None

    def _should_flush(self) -> bool:
        threshold = self._get_threshold()
        if self.bar_type == "volume":
            return self.cumulative_volume >= threshold
        elif self.bar_type == "dollar":
            return self.cumulative_dollar >= threshold
        elif self.bar_type == "tick":
            return self.tick_count >= threshold
        return False

    def _get_threshold(self) -> float:
        if self.threshold is not None:
            return self.threshold
        defaults = {"volume": 500.0, "dollar": 50000.0, "tick": 500, "time": 900000}
        return defaults.get(self.bar_type, 500.0)

    def _flush(self) -> dict | None:
        if self._open is None:
            return None

        bar = {
            "symbol": self._symbol,
            "timestamp": self._timestamp,
            "open": self._open,
            "high": self._high,
            "low": self._low,
            "close": self._close,
            "base_volume": self._base_volume,
            "quote_volume": self._quote_volume,
            "trades": self.tick_count,
            "bar_type": self.bar_type,
        }

        self._open = None
        self._high = -float("inf")
        self._low = float("inf")
        self._close = None
        self._base_volume = 0.0
        self._quote_volume = 0.0
        self.tick_count = 0
        self.cumulative_volume = 0.0
        self.cumulative_dollar = 0.0

        return bar

    def estimate_threshold(self, ticker_data: list, percentile: float = 95.0) -> float:
        """Estimate bar threshold from historical ticker volume data."""
        if not ticker_data:
            return self._get_threshold()
        volumes = [t.get("baseVolume", t.get("volume", 0)) for t in ticker_data]
        volumes = [v for v in volumes if v > 0]
        if not volumes:
            return self._get_threshold()
        return float(np.percentile(volumes, percentile))


def volume_bar_threshold(daily_volume: float, expected_bars_per_day: int = 100) -> float:
    """Heuristic: set volume bar threshold based on 24h volume."""
    return daily_volume / expected_bars_per_day


def dollar_bar_threshold(daily_volume: float, avg_price: float, expected_bars_per_day: int = 100) -> float:
    """Heuristic: set dollar bar threshold based on 24h dollar volume."""
    return (daily_volume * avg_price) / expected_bars_per_day


def candles_to_info_bars(candles: list, bar_type: str = "volume",
                         threshold: float | None = None) -> list[dict]:
    """Convert time-based OHLCV candles into information-driven bars.

    Takes ccxt-style candles [[ts, o, h, l, c, v], ...] and aggregates
    them by volume/dollar/tick thresholds. Returns bars in the same
    [ts, o, h, l, c, v] format for drop-in replacement.
    """
    if not candles:
        return []

    bars = InformationBars(bar_type=bar_type, threshold=threshold)
    result = []
    daily_volumes = [c[5] for c in candles if isinstance(c, (list, tuple)) and len(c) >= 6]
    avg_vol = sum(daily_volumes) / len(daily_volumes) if daily_volumes else 1.0

    if threshold is None and bar_type == "volume":
        bars.threshold = avg_vol * 3
    elif threshold is None and bar_type == "dollar":
        avg_price = candles[-1][4] if candles and len(candles[-1]) >= 5 else 1.0
        bars.threshold = avg_vol * 3 * avg_price

    for candle in candles:
        if not isinstance(candle, (list, tuple)) or len(candle) < 6:
            continue
        ts, o, h, l, c, v = candle[0], candle[1], candle[2], candle[3], candle[4], candle[5]

        bar = bars.add_tick(price=c, volume=v, timestamp=int(ts))
        if bar:
            result.append([
                int(bar["timestamp"]),
                bar["open"],
                bar["high"],
                bar["low"],
                bar["close"],
                bar["base_volume"],
            ])

    last = bars._flush()
    if last and last["base_volume"] > 0 and last["close"] is not None:
        result.append([
            int(last["timestamp"]),
            last["open"],
            last["high"],
            last["low"],
            last["close"],
            last["base_volume"],
        ])

    return result


def build_info_bar_market_data(exchange, symbol: str, bar_type: str = "volume",
                                target_count: int = 50,
                                candles: list | None = None) -> dict:
    """Convert OHLCV to info bars, compute indicators — drop-in for _build_market_data.

    Pass ``candles`` (ccxt-style [[ts,o,h,l,c,v],...]) to reuse an existing
    fetch; otherwise it fetches 15m itself. Returns dict keyed by bar_type
    string (e.g. {'volume': {indicators...}}) that can be passed to
    SignalEngine.evaluate().
    """
    try:
        raw = candles if candles is not None else exchange.fetch_ohlcv(symbol, "15m", limit=300)
        if not raw or len(raw) < 20:
            return {}
        info_candles = candles_to_info_bars(raw, bar_type=bar_type)
        if len(info_candles) < 20:
            return {}
        info_candles = info_candles[-target_count:]
    except Exception as e:
        logger.debug(f"Info bars {symbol}: {e}")
        return {}

    closes = np.array([c[4] for c in info_candles], dtype=float)
    highs = np.array([c[2] for c in info_candles], dtype=float)
    lows = np.array([c[3] for c in info_candles], dtype=float)
    volumes = np.array([c[5] for c in info_candles], dtype=float)
    last = info_candles[-1]

    atr = float(np.mean(highs[-14:] - lows[-14:])) if len(info_candles) >= 14 else 0
    atr_pct = atr / last[4] if last[4] > 0 else 0.02
    sma20 = float(np.mean(closes[-20:])) if len(closes) >= 20 else last[4]
    sma50 = float(np.mean(closes[-50:])) if len(closes) >= 50 else last[4]
    std20 = float(np.std(closes[-20:])) if len(closes) >= 20 else 0
    vol_ratio = float(last[5] / np.mean(volumes[-20:])) if np.mean(volumes[-20:]) > 0 else 1.0

    deltas = np.diff(closes)
    gains = np.maximum(deltas, 0)
    losses = np.abs(np.minimum(deltas, 0))
    avg_gain = float(np.mean(gains[-14:]) if len(gains) >= 14 else 0)
    avg_loss = float(np.mean(losses[-14:]) if len(losses) >= 14 else 0)
    rsi_val = 100.0 - (100.0 / (1 + avg_gain / avg_loss)) if avg_loss > 0 else 100.0

    def _ema(prices, period):
        if len(prices) < period:
            return None
        alpha = 2 / (period + 1)
        ema = prices[0]
        for p in prices[1:]:
            ema = alpha * p + (1 - alpha) * ema
        return float(ema)

    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd = ema12 - ema26 if ema12 and ema26 else None

    def _adx(h, l, c, period=14):
        if len(h) < period + 1:
            return 20.0
        h, l, c = h[-period-1:], l[-period-1:], c[-period-1:]
        prev_c = np.roll(c, 1)
        tr = np.maximum(h - l, np.maximum(abs(h - prev_c), abs(l - prev_c)))[1:]
        atr_val = np.mean(tr[-period:]) if len(tr) >= period else 1.0
        if atr_val == 0:
            return 20.0
        up = np.maximum(0, h[1:] - h[:-1])
        dn = np.maximum(0, l[:-1] - l[1:])
        plus_di = 100 * np.mean(up[-period:]) / atr_val
        minus_di = 100 * np.mean(dn[-period:]) / atr_val
        dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) > 0 else 0
        return float(dx)

    adx_val = _adx(highs, lows, closes)

    return {
        bar_type: {
            "open": float(last[1]), "high": float(last[2]),
            "low": float(last[3]), "close": float(last[4]),
            "volume": float(last[5]),
            "atr": round(atr, 6), "atr_pct": round(atr_pct, 4),
            "sma20": round(sma20, 6), "sma50": round(sma50, 6),
            "bb_upper": round(sma20 + std20 * 2, 6),
            "bb_lower": round(sma20 - std20 * 2, 6),
            "rsi": round(rsi_val, 1), "adx": round(adx_val, 1),
            "macd": round(macd, 6) if macd else None,
            "macd_signal": round(macd_sig, 6) if (macd_sig := (_ema(np.array([macd]), 9) if macd else None)) else None,
            "volatility_15m": round(abs((last[4] - closes[-2]) / closes[-2] * 100), 2) if len(closes) >= 2 else 0,
            "volume_ratio": round(vol_ratio, 2),
            "sma20_distance": round((last[4] - sma20) / std20, 2) if std20 > 0 else 0,
            "hour": float(datetime.utcnow().hour),  # UTC — must match meta-retrain hour
            "bar_count": len(info_candles),
        }
    }
