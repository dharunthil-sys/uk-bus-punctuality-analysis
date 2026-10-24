"""Tests use a synthetic workbook shaped like DfT's BUS09 release, not real data."""
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import analyse  # noqa: E402
import fetch_data  # noqa: E402

YEARS = ["2016/17", "2017/18", "2018/19", "2019/20", "2020/21", "2021/22", "2022/23", "2023/24"]


def make_ods() -> bytes:
    rng = np.random.default_rng(3)
    areas = [f"Test Council {i}" for i in range(30)]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="odf") as xw:
        pd.DataFrame({"Cover": ["Bus statistics (synthetic test file)"]}).to_excel(xw, sheet_name="Cover", index=False)
        # Frequent services: excess waiting time in minutes, not a percentage
        ewt = pd.DataFrame([["Table BUS0903: Average excess waiting time, frequent services (minutes)"], [None]])
        ewt.to_excel(xw, sheet_name="BUS0903", index=False, header=False)
        pd.DataFrame({"Local authority": areas, **{y: rng.uniform(0.5, 2, 30).round(2) for y in YEARS}}).to_excel(
            xw, sheet_name="BUS0903", index=False, startrow=3)
        # Non-frequent services: % on time, with codes, an England row and suppressed cells
        title = pd.DataFrame([["Table BUS0902: Percentage of non-frequent bus services running on time by local authority: England"],
                              ["Source: synthetic"], [None]])
        title.to_excel(xw, sheet_name="BUS0902", index=False, header=False)
        body = pd.DataFrame({"Local authority code": ["E92000001"] + [f"E06{i:06d}" for i in range(30)],
                             "Local authority": ["England"] + areas,
                             **{f"{y} [note 2]": [80.0] + list(rng.uniform(70, 90, 30).round(1)) for y in YEARS}})
        col = body.columns[3]
        body[col] = body[col].astype(object)
        body.loc[5, col] = "[x]"
        body.to_excel(xw, sheet_name="BUS0902", index=False, startrow=4)
    return buf.getvalue()


def test_year_label():
    assert fetch_data.year_label("2009/10 [note 3]") == "2009/10"
    assert fetch_data.year_label("2019") == "2019"
    assert fetch_data.year_label("Local authority") is None


def test_parse_picks_non_frequent_sheet():
    long, log = fetch_data.parse(make_ods())
    assert any("Chosen sheet: BUS0902" in line for line in log)
    assert set(long["year"]) == set(YEARS)
    assert long["pct_on_time"].between(0, 100).all()
    assert long["area_code"].notna().all()
    assert len(long) == 31 * 8 - 1  # one suppressed [x] cell dropped


def test_analysis_end_to_end(tmp_path, monkeypatch=None):
    long, _ = fetch_data.parse(make_ods())
    (tmp_path / "data").mkdir()
    long.to_csv(tmp_path / "data" / "punctuality_long.csv", index=False)
    analyse.ROOT = tmp_path
    analyse.main()
    text = (tmp_path / "results" / "summary.md").read_text()
    assert "England: **80.0%**" in text
    assert "England" not in pd.read_csv(tmp_path / "results" / "area_changes.csv")["area"].tolist()
