# UK Bus Punctuality Analysis

How punctual are England's local bus services, which areas are getting worse, and has the gap between the best and worst areas grown since before the pandemic?

**Results:** see [`results/summary.md`](results/summary.md) for the national trend, the most and least punctual areas, the biggest changes since 2018/19, and the charts.

## Data

Department for Transport, [Bus statistics data tables](https://www.gov.uk/government/statistical-data-sets/bus-statistics-data-tables), table **BUS09: Bus reliability and punctuality**. The measure is the percentage of *non-frequent* services (fewer than six buses an hour) running on time, by local authority, each year.

[`src/fetch_data.py`](src/fetch_data.py) downloads the latest BUS09 file, finds the local-authority punctuality table, and reshapes it into [`data/punctuality_long.csv`](data/punctuality_long.csv): one row per area per year. That tidy file loads straight into Excel or Power BI. Suppressed or missing cells (DfT marks them `[x]`, `[z]`, `[c]`) are dropped rather than treated as zero. [`data/PARSE_LOG.txt`](data/PARSE_LOG.txt) records which sheet was used.

The workflow in `.github/workflows/update.yml` re-downloads the data and rebuilds the results every month, so the analysis picks up each new DfT release.

## Method

- **National trend:** England's figure where DfT publishes it, with the spread of individual areas (10th to 90th percentile) shown behind it.
- **Rankings:** local authorities only. Regional and national totals are removed (by name and by ONS code prefix) so they don't appear as "areas".
- **Recovery:** each area's latest figure compared with 2018/19, the last full year before COVID-19.
- **Inequality between areas:** the gap between the 90th and 10th percentile area, year by year.

## Limitations

- Local authorities monitor punctuality in different ways and with different sample sizes, so small year-to-year changes in one area may be noise.
- "On time" for non-frequent services means between one minute early and five minutes late. It says nothing about frequent services, where DfT measures excess waiting time instead.
- The figures show *where* punctuality changed, not *why*. Linking them to congestion, roadworks or bus funding would be the next step.

## Run it yourself

```bash
pip install -r requirements.txt
python src/fetch_data.py
python src/analyse.py
pytest   # tests run on a synthetic workbook shaped like the DfT file
```
