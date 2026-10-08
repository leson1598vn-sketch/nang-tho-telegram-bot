"""Vietnamese UI formatters: compact numbers, VND, durations, tables."""
from __future__ import annotations


def fmt_num(n) -> str:
    n = int(n or 0)
    if n >= 1_000_000_000:
        return f"{n / 1e9:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1e6:.1f}M"
    if n >= 1_000:
        return f"{n / 1e3:.1f}K"
    return str(n)


def fmt_int(n) -> str:
    return f"{int(n or 0):,}".replace(",", ".")


def fmt_vnd(n) -> str:
    return f"{fmt_int(n)} ₫"


def fmt_watch(ms) -> str:
    """ms -> m:ss"""
    s = int((ms or 0) // 1000)
    return f"{s // 60}:{s % 60:02d}"


def pct(a, b) -> str:
    if not b:
        return "0%"
    return f"{100 * a / b:.1f}%"


def short(s: str, n: int = 34) -> str:
    s = str(s or "")
    return s if len(s) <= n else s[: n - 1] + "…"


def code_table(headers: list[str], rows: list[list[str]]) -> str:
    """Compact monospaced table inside a code block."""
    widths = [len(h) for h in headers]
    for r in rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], len(str(cell)))
    def line(cells):
        return " ".join(str(c).ljust(widths[i]) for i, c in enumerate(cells)).rstrip()
    out = [line(headers), line(["-" * w for w in widths])]
    out += [line(r) for r in rows]
    return "<pre>" + "\n".join(out) + "</pre>"


def fmt_dt_local(dt, fmt: str = "%d/%m %H:%M") -> str:
    if dt is None:
        return "—"
    return dt.strftime(fmt)
