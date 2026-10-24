"""Download DfT table BUS09 (bus reliability and punctuality) and reshape the
local-authority punctuality table into a tidy long file.

Source: Department for Transport, Bus statistics data tables, BUS09
https://www.gov.uk/government/statistical-data-sets/bus-statistics-data-tables

Run:  python src/fetch_data.py
Writes data/raw/bus09.ods, data/punctuality_long.csv (one row per area per year,
ready for pandas, Excel or Power BI) and data/PARSE_LOG.txt.
"""
from __future__ import annotations

import io
import re
import sys
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PAGE = "https://www.gov.uk/government/statistical-data-sets/bus-statistics-data-tables"
FALLBACK = "https://assets.publishing.service.gov.uk/media/69c11f97cfa346b9d4704a52/bus09.ods"
HEADERS = {"User-Agent": "Mozilla/5.0 (uk-bus-punctuality-analysis; github.com/dharunthil-sys)"}
YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?:\s*/\s*(\d{2,4}))?")
AREA_WORDS = ("local authority", "area", "authority", "region")


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def latest_url() -> str:
    try:
        html = get(PAGE).decode("utf-8", "replace")
        links = re.findall(r'href="(https://assets\.publishing\.service\.gov\.uk/[^"]*/bus09\.ods)"', html)
        if links:
            return links[0]
    except Exception as exc:
        print(f"Could not read DfT page ({exc}); using known file URL", file=sys.stderr)
    return FALLBACK


def year_label(cell: str) -> str | None:
    """'2009/10 [note 3]' -> '2009/10'; '2019' -> '2019'. None if not a year column."""
    m = YEAR.search(cell)
    if not m or len(cell) > 40:
        return None
    start, end = m.group(1), m.group(2)
    return f"{start}/{end[-2:]}" if end else start


def to_number(x) -> float | None:
    if pd.isna(x):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace("%", "")
    try:
        return float(s)
    except ValueError:
        return None  # DfT uses [x], [z], [c], '..' for missing or suppressed values


def find_table(raw: pd.DataFrame) -> tuple[int, int, dict[int, str]] | None:
    """Return (header_row, area_col, {col: year}) for a sheet laid out areas x years."""
    for r in range(min(40, len(raw))):
        cells = ["" if pd.isna(x) else str(x).strip() for x in raw.iloc[r]]
        years = {j: y for j, c in enumerate(cells) if (y := year_label(c))}
        area_cols = [j for j, c in enumerate(cells)
                     if any(w in c.lower() for w in AREA_WORDS) and "code" not in c.lower()]
        if len(years) >= 3 and area_cols:
            return r, area_cols[0], years
    return None


def is_percentage_table(values: pd.Series) -> bool:
    v = values.dropna()
    return len(v) > 20 and v.between(0, 100).mean() > 0.95 and v.median() > 30


def parse(content: bytes) -> tuple[pd.DataFrame, list[str]]:
    sheets = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None, engine="odf")
    log = [f"Sheets: {list(sheets)}"]
    candidates = []
    for name, raw in sheets.items():
        title = " ".join(str(x) for x in raw.iloc[:6, 0].dropna()).lower()
        found = find_table(raw)
        log.append(f"- {name}: title='{title[:120]}' table={'yes' if found else 'no'}")
        if not found:
            continue
        hr, ac, years = found
        rows = []
        for _, row in raw.iloc[hr + 1:].iterrows():
            area = row.iloc[ac]
            if pd.isna(area) or not str(area).strip():
                continue
            for j, y in years.items():
                rows.append({"area": str(area).strip(), "year": y, "pct_on_time": to_number(row.iloc[j])})
        long = pd.DataFrame(rows)
        if long.empty:
            continue
        code_col = next((j for j, c in enumerate(raw.iloc[hr]) if isinstance(c, str) and "code" in c.lower()), None)
        if code_col is not None:
            codes = raw.iloc[hr + 1:, [ac, code_col]].dropna()
            long = long.merge(pd.DataFrame({"area": codes.iloc[:, 0].astype(str).str.strip(),
                                            "area_code": codes.iloc[:, 1].astype(str).str.strip()}).drop_duplicates("area"),
                              on="area", how="left")
        score = (("non-frequent" in title or "non frequent" in title) * 10
                 + ("on time" in title) * 5 + ("local authority" in title) * 3
                 + is_percentage_table(long["pct_on_time"]) * 4)
        candidates.append((score, name, title, long))
    if not candidates:
        raise ValueError("No area-by-year table found in BUS09.\n" + "\n".join(log))
    score, name, title, long = max(candidates, key=lambda c: c[0])
    log.append(f"Chosen sheet: {name} (score {score}): {title[:200]}")
    long = long.dropna(subset=["pct_on_time"])
    long = long[~long["area"].str.lower().str.startswith(("source", "note", "[note"))]
    return long, log


def main() -> None:
    raw_dir = ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    url = latest_url()
    print(f"Downloading {url}")
    content = get(url)
    (raw_dir / "bus09.ods").write_bytes(content)
    long, log = parse(content)
    long.to_csv(ROOT / "data" / "punctuality_long.csv", index=False)
    (ROOT / "data" / "PARSE_LOG.txt").write_text(f"Source: {url}\n" + "\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log))
    print(f"Wrote {len(long)} rows: {long['area'].nunique()} areas, years {long['year'].min()} to {long['year'].max()}")


if __name__ == "__main__":
    main()
