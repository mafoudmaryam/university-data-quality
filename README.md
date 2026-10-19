# University data quality research

How does poor-quality data affect the reliability of information systems?

A controlled experiment on a synthetic university database (students, courses, enrolments): known errors are injected (duplicates, missing, outdated, inconsistent values), detected with 19 rule-based checks grouped by data-quality dimension, cleaned, and error rates are compared before and after against ground truth.

See [report.md](report.md) for the research plan, results and data-governance review, and [docs/explained.md](docs/explained.md) for a plain-language walkthrough.

## Run

```
pip install pandas
cd src && python3 evaluate.py
```

This regenerates `data/` and writes all result tables to `results/`.
