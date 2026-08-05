"""Indian Crypto Tax Journal — Section 115BBH + Section 194S compliance.

Rules:
  - 30% flat tax on ALL crypto gains (Section 115BBH). No slab benefit.
  - 1% TDS per transaction where gross value ≥ ₹10,000 (Section 194S).
  - Losses CANNOT offset gains. Each profitable trade taxed independently.
  - Holding period irrelevant — all crypto is short-term capital gains.
  - Export to CSV for Chartered Accountant filing.

Connected to DuckDB trades table. All values auto-converted to INR.
"""

import csv
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger

INR_RATE = 83.12  # USD to INR fallback rate


class TaxCalculator:
    def __init__(self, store, inr_rate: float = INR_RATE, currency: str = "INR"):
        self.store = store
        self.inr_rate = inr_rate
        self.currency = currency
        self.sym = "₹" if currency == "INR" else "$"

    def compute_tax_liability(self, year: int | None = None) -> dict:
        """Calculate total taxable gains, TDS, and net payable for a tax year.

        Returns a dict with: total_realized_gains, taxable_gains, tax_30pct,
        total_tds_1pct, net_payable, profitable_trades, loss_trades.
        """
        rows = self._fetch_closed_trades(year)
        if not rows:
            return self._empty_result()

        profitable_trades = []
        loss_trades = []
        tds_transactions = []

        for row in rows:
            pnl = float(row["pnl"] or 0)
            gross_value = float(row["usdt_value"] or 0)
            pnl_inr = pnl * self.inr_rate
            value_inr = gross_value * self.inr_rate

            if pnl_inr > 0:
                profitable_trades.append({
                    "symbol": row.get("symbol", "?"),
                    "entry_time": row.get("entry_time", 0),
                    "exit_time": row.get("exit_time", 0),
                    "pnl_inr": round(pnl_inr, 2),
                    "tax_30pct": round(pnl_inr * 0.30, 2),
                })
            else:
                loss_trades.append({
                    "symbol": row.get("symbol", "?"),
                    "pnl_inr": round(pnl_inr, 2),
                })

            if value_inr >= 10000:
                tds_transactions.append({
                    "symbol": row.get("symbol", "?"),
                    "gross_value_inr": round(value_inr, 2),
                    "tds_1pct": round(value_inr * 0.01, 2),
                    "entry_time": row.get("entry_time", 0),
                })

        total_gains = sum(t["pnl_inr"] for t in profitable_trades)
        taxable_gains = total_gains  # losses don't offset
        tax_30pct = taxable_gains * 0.30
        total_tds = sum(t["tds_1pct"] for t in tds_transactions)
        net_payable = max(0, tax_30pct - total_tds)

        return {
            "tax_year": year or datetime.now().year,
            "currency": self.currency,
            "inr_rate": self.inr_rate,
            "total_trades": len(profitable_trades) + len(loss_trades),
            "profitable_trades": len(profitable_trades),
            "loss_trades": len(loss_trades),
            "total_realized_gains": round(total_gains, 2),
            "taxable_gains": round(taxable_gains, 2),
            "tax_30pct": round(tax_30pct, 2),
            "total_tds_1pct": round(total_tds, 2),
            "tds_transactions_count": len(tds_transactions),
            "net_payable": round(net_payable, 2),
            "losses_ignored": sum(abs(t["pnl_inr"]) for t in loss_trades),
            "note": "Losses CANNOT offset gains under Section 115BBH.",
            "profitable_details": profitable_trades,
            "loss_details": loss_trades,
            "tds_details": tds_transactions,
        }

    def generate_itr_schedule(self, year: int | None = None) -> str:
        """Formatted text table for ITR Schedule VDA (Virtual Digital Assets)."""
        liability = self.compute_tax_liability(year)
        if not liability.get("total_trades"):
            return "No trades to report."

        lines = [
            "=" * 72,
            f"   KAIRO TRADING BOT — TAX SCHEDULE (FY {liability['tax_year']})",
            "=" * 72,
            "",
            f"  Currency: {liability['currency']} | Rate: {self.sym}{liability['inr_rate']}/USD",
            f"  Total Trades: {liability['total_trades']}",
            f"  Profitable: {liability['profitable_trades']} | Losses: {liability['loss_trades']}",
            "",
            "-" * 72,
            "  SCHEDULE VDA — Virtual Digital Assets",
            "-" * 72,
            "",
            f"  A. Total consideration received on transfer:  {self.sym}{liability['total_realized_gains']:,.2f}",
            f"  B. Cost of acquisition (deductible):           {self.sym}0.00 (no cost basis for crypto)",
            f"  C. Income chargeable under head 'Capital Gains': {self.sym}{liability['taxable_gains']:,.2f}",
            f"  D. Tax @ 30% (Section 115BBH):                 {self.sym}{liability['tax_30pct']:,.2f}",
            f"  E. Less: TDS already deducted (Section 194S):  {self.sym}{liability['total_tds_1pct']:,.2f}",
            f"  F. Net tax payable:                             {self.sym}{liability['net_payable']:,.2f}",
            "",
            "-" * 72,
            "  PROFITABLE TRADE DETAILS",
            "-" * 72,
        ]
        for i, t in enumerate(liability.get("profitable_details", []), 1):
            dt = datetime.fromtimestamp(t["entry_time"] / 1000).strftime("%d-%b-%Y") if t["entry_time"] else "?"
            lines.append(f"  {i:3d}. {t['symbol']:10s}  {dt}  P&L: {self.sym}{t['pnl_inr']:>10,.2f}  Tax: {self.sym}{t['tax_30pct']:>10,.2f}")

        if liability.get("tds_details"):
            lines.append("")
            lines.append("-" * 72)
            lines.append("  TDS TRANSACTIONS (Section 194S — 1% on ≥₹10,000)")
            lines.append("-" * 72)
            for i, t in enumerate(liability["tds_details"], 1):
                dt = datetime.fromtimestamp(t["entry_time"] / 1000).strftime("%d-%b-%Y") if t["entry_time"] else "?"
                lines.append(f"  {i:3d}. {t['symbol']:10s}  {dt}  Value: {self.sym}{t['gross_value_inr']:>10,.2f}  TDS: {self.sym}{t['tds_1pct']:>10,.2f}")

        lines.append("")
        lines.append(f"  ⚠ Losses of {self.sym}{liability['losses_ignored']:,.2f} cannot offset gains (Section 115BBH)")
        lines.append("=" * 72)
        return "\n".join(lines)

    def export_csv(self, output_path: str | Path, year: int | None = None) -> str:
        """Export tax data to CSV for Chartered Accountant."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        liability = self.compute_tax_liability(year)

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Kairo Trading Bot — Tax Export", f"FY {liability['tax_year']}", f"Generated: {datetime.now().isoformat()}"])
            writer.writerow([])
            writer.writerow(["Section", "Amount (INR)"])
            writer.writerow(["Total Realized Gains", liability["total_realized_gains"]])
            writer.writerow(["Tax @ 30% (115BBH)", liability["tax_30pct"]])
            writer.writerow(["TDS Deducted (194S)", liability["total_tds_1pct"]])
            writer.writerow(["Net Payable", liability["net_payable"]])
            writer.writerow([])
            writer.writerow(["Symbol", "Entry Date", "P&L (INR)", "Tax 30%", "TDS 1%", "Gross Value (INR)"])
            for t in liability.get("profitable_details", []):
                dt = datetime.fromtimestamp(t["entry_time"] / 1000).strftime("%Y-%m-%d") if t["entry_time"] else ""
                writer.writerow([t["symbol"], dt, t["pnl_inr"], t["tax_30pct"], "", ""])
            for t in liability.get("tds_details", []):
                dt = datetime.fromtimestamp(t["entry_time"] / 1000).strftime("%Y-%m-%d") if t["entry_time"] else ""
                writer.writerow([t["symbol"], dt, "", "", t["tds_1pct"], t["gross_value_inr"]])

        logger.info(f"Tax CSV exported: {output_path}")
        return str(output_path)

    def get_monthly_summary(self, year: int | None = None) -> list[dict]:
        """Month-wise tax breakdown for dashboard."""
        rows = self._fetch_closed_trades(year)
        if not rows:
            return []

        months = {}
        for row in rows:
            ts = row.get("exit_time") or row.get("entry_time", 0)
            if not ts:
                continue
            dt = datetime.fromtimestamp(ts / 1000)
            key = dt.strftime("%Y-%m")
            pnl = float(row["pnl"] or 0) * self.inr_rate
            value = float(row["usdt_value"] or 0) * self.inr_rate

            if key not in months:
                months[key] = {"profits": 0, "losses": 0, "tds": 0, "trades": 0}
            months[key]["trades"] += 1
            if pnl > 0:
                months[key]["profits"] += pnl
            else:
                months[key]["losses"] += abs(pnl)
            if value >= 10000:
                months[key]["tds"] += value * 0.01

        return [
            {
                "month": k,
                "profitable_pnl": round(v["profits"], 2),
                "losses": round(v["losses"], 2),
                "tax_due": round(v["profits"] * 0.30, 2),
                "tds_paid": round(v["tds"], 2),
                "trades": v["trades"],
            }
            for k, v in sorted(months.items())
        ]

    def _fetch_closed_trades(self, year: int | None = None) -> list[dict]:
        if year:
            start_ts = int(datetime(year, 1, 1).timestamp() * 1000)
            end_ts = int(datetime(year + 1, 1, 1).timestamp() * 1000)
            result = self.store.conn.execute(
                "SELECT * FROM trades WHERE status='closed' AND entry_time >= ? AND entry_time < ? ORDER BY exit_time DESC",
                [start_ts, end_ts],
            ).fetchdf()
        else:
            result = self.store.conn.execute(
                "SELECT * FROM trades WHERE status='closed' AND pnl IS NOT NULL ORDER BY exit_time DESC"
            ).fetchdf()
        return result.to_dict("records") if len(result) > 0 else []

    @staticmethod
    def _empty_result() -> dict:
        return {
            "tax_year": datetime.now().year,
            "total_trades": 0, "profitable_trades": 0, "loss_trades": 0,
            "total_realized_gains": 0, "taxable_gains": 0, "tax_30pct": 0,
            "total_tds_1pct": 0, "tds_transactions_count": 0, "net_payable": 0,
            "losses_ignored": 0, "profitable_details": [], "loss_details": [], "tds_details": [],
            "note": "Losses CANNOT offset gains under Section 115BBH.",
        }
