"""Kairo — live sizing calculator.

Shows exactly how the ACTIVE risk profile (config/risk_rules.yaml profiles)
maps to real position sizes across regimes and meta-labeler confidence, using
the exact production sizing code path (RiskManagerAgent). Tweak the profile
numbers in config/risk_rules.yaml, re-run, and see the impact instantly.

Usage:
    python scripts/sizing_calc.py                     # active mode, live balance
    python scripts/sizing_calc.py --mode aggressive   # force a profile
    python scripts/sizing_calc.py --balance 10000 --price 200 --atr 4.0
"""

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.risk_manager import RiskManagerAgent
from src.config.state_manager import deep_merge

REGIMES = ["strong_trend", "weak_trend", "choppy", "high_vol", "mean_reverting"]
META_P = [0.55, 0.7, 0.9]


class _StaticState:
    """Minimal stand-in for RuntimeStateManager — no persistence, no poller."""

    def __init__(self, params: dict):
        self._params = params

    def get_active_params(self) -> dict:
        return self._params


def load_params(mode: str) -> dict:
    with open("config/risk_rules.yaml") as fh:
        rules = yaml.safe_load(fh) or {}
    base = {k: v for k, v in rules.items() if k != "profiles"}
    profile = (rules.get("profiles") or {}).get(mode) or {}
    params = deep_merge(base, profile)
    params["mode"] = mode
    return params


def live_balance() -> float:
    try:
        import httpx
        r = httpx.get("http://127.0.0.1:8000/status", timeout=3)
        return float(r.json().get("balance", 0)) if r.status_code == 200 else 0.0
    except Exception:
        return 0.0


def build_trade(params: dict, symbol: str, price: float, atr: float, regime: str, p: float):
    sizing = params.get("sizing", {})
    pre_trade = params.get("pre_trade", {})
    atr_pct = atr / price if price > 0 else 0.0075
    sl_mult = float(sizing.get("sl_atr_multiplier", 2.0))
    tp_mult = float(sizing.get("tp_atr_multiplier", 4.0))
    min_rr = float(pre_trade.get("min_risk_reward_ratio", 1.5))
    min_sl = float(sizing.get("min_sl_pct", 0.015))
    min_tp = float(sizing.get("min_tp_pct", 0.03))
    sl_pct = max(atr_pct * sl_mult, min_sl)
    tp_pct = max(atr_pct * tp_mult, sl_pct * min_rr, min_tp)
    return {
        "symbol": symbol, "action": "LONG", "entry_price": price,
        "stop_loss": price * (1 - sl_pct), "take_profit": price * (1 + tp_pct),
        "stop_loss_pct": sl_pct, "take_profit_pct": tp_pct,
        "regime": regime, "confidence": 0.8,
        "meta_probability": p, "risk_multiplier": 1.0,
    }


def main():
    ap = argparse.ArgumentParser(description="Show how the active profile sizes positions.")
    ap.add_argument("--mode", default=None, help="Profile to compute (default: active mode)")
    ap.add_argument("--balance", type=float, default=None, help="Account balance USDT (default: live bot balance)")
    ap.add_argument("--symbol", default="BTC/USDT")
    ap.add_argument("--price", type=float, default=63488.0)
    ap.add_argument("--atr", type=float, default=450.0)
    ap.add_argument("--vanilla", action="store_true", help="Also print the vanilla comparison column")
    args = ap.parse_args()

    with open("config/risk_rules.yaml") as fh:
        rules = yaml.safe_load(fh) or {}
    modes = [args.mode] if args.mode else [m for m in ("aggressive", "vanilla") if m in (rules.get("profiles") or {})]
    # If no --mode given, prefer showing aggressive first (that's what we're tuning),
    # but respect the bot's live mode if it's not aggressive.
    if not args.mode:
        modes = ["aggressive", "vanilla"]

    balance = args.balance if args.balance else live_balance() or 5000.0

    for mode in modes:
        params = load_params(mode)
        rm = RiskManagerAgent(None, _StaticState(params))
        pre_trade = params.get("pre_trade", {})
        sizing = params.get("sizing", {})
        micro = params.get("micro_capital", {})
        regime_mults = params.get("regime_multipliers", {})

        print("=" * 78)
        print(f"PROFILE: {mode.upper()}   | balance=${balance:,.2f}  {args.symbol} @ {args.price} (ATR {args.atr})")
        print(f"  max_pos {pre_trade.get('max_position_pct')}% | min_conf {pre_trade.get('min_confidence')} | "
              f"kelly x{sizing.get('kelly_fraction')} | risk/trade {float(sizing.get('vol_target_risk_pct', 0)) * 100:.1f}% | "
              f"SL {sizing.get('sl_atr_multiplier')}xATR (floor {float(sizing.get('min_sl_pct', 0))*100:.1f}%) | "
              f"TP {sizing.get('tp_atr_multiplier')}xATR | minR:R {pre_trade.get('min_risk_reward_ratio')} | "
              f"conviction x{float(sizing.get('conviction_scale', 0)):.1f} (max {float(sizing.get('conviction_max_mult', 1.5)):.1f})")
        if micro.get("enabled"):
            eff = max(float(pre_trade.get("max_position_pct", 2.0)),
                      float(micro.get("min_meaningful_order_usdt", 5.0)) / balance * 100
                      if balance < float(micro.get("balance_threshold", 2000)) else 0)
            cap_note = f" | micro: threshold ${micro.get('balance_threshold')}, ceiling {micro.get('max_position_pct')}%"
        else:
            cap_note = ""
        print(f"  regime mults: " + ", ".join(f"{r}={m}" for r, m in regime_mults.items()))
        print("-" * 78)
        print(f"{'regime':<16}{'M':>5} | " + " | ".join(f"p={p:.2f}".ljust(11) for p in META_P) + " | binder")
        print("-" * 78)

        for regime in REGIMES:
            cells = []
            binders = set()
            for p in META_P:
                trade = build_trade(params, args.symbol, args.price, args.atr, regime, p)
                result = rm.size_position(trade, {"balance": balance, "open_positions": 0, "scorecard": {}},
                                          {"15m": {"atr": args.atr, "atr_pct": args.atr / args.price}})
                if result["decision"] != "SIZED":
                    cells.append("REJECTED".ljust(11))
                else:
                    cells.append(f"${result['size_usdt']:,.2f}".ljust(11))
                    sm = result["trade"].get("sizing_method", {})
                    binders.add(sm.get("vol_targeted") is not None and sm.get("kelly") is not None and sm.get("max_allowed") is not None)
                    # crude binder: which of the three pre-multiplier candidates was smallest
                    parts = [(sm.get("vol_targeted") or 0, "vol"), (sm.get("kelly") or 0, "kelly"), (sm.get("max_allowed") or 0, "cap")]
                    parts = [x for x in parts if x[0] > 0]
                    if parts:
                        binder, _ = min(parts, key=lambda x: x[0])
                        if abs(binder - sm.get("final", 0)) < 1:
                            pass  # final includes mult/clamp; binder name kept below
            # compute binder + pressed cap from the p=0.7 case for the row
            t = build_trade(params, args.symbol, args.price, args.atr, regime, 0.7)
            r = rm.size_position(t, {"balance": balance, "open_positions": 0, "scorecard": {}},
                                 {"15m": {"atr": args.atr, "atr_pct": args.atr / args.price}})
            sm = r.get("trade", {}).get("sizing_method", {})
            parts = [(sm.get("vol_targeted") or 0, "vol"), (sm.get("kelly") or 0, "kelly"), (sm.get("max_allowed") or 0, "cap")]
            parts = [x for x in parts if x[0] > 0]
            binder = min(parts, key=lambda x: x[0])[1] if parts else "?"
            mult = float(regime_mults.get(regime, 1.0))
            m_regime_note = f"x{mult}" if mult != 1.0 else "-"
            print(f"{regime:<16}{m_regime_note:>5} | " + " | ".join(cells) + f" | {binder}")
        print()

    print("Note: binder = smallest of (vol-targeted, Kelly, position cap); final = binder x conviction x M_regime, clamped to cap x conviction x max(M,1).")


if __name__ == "__main__":
    main()
