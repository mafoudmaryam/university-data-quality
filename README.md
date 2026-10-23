# University data quality research

Author: Maryam Mafoud

**Research question:** How does poor-quality data affect the reliability of information systems?

A controlled synthetic university experiment measures duplicates, incomplete fields, outdated records, inconsistent codes and formats, invalid values and broken links. It compares rule flags, actual accuracy and nine reporting metrics before and after conservative cleaning.

Suspected outdated records go to a review queue. The program does not assume that an overdue student has graduated. Results include 30 repeated mixed-error runs, 24 isolated-family scenarios and a zero-error control.

## Setup and run

Python 3.11+; tested with pandas 2.2.3 and NumPy 2.3.5.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python src/evaluate.py
python src/experiments.py
```

The pilot regenerates `data/` and pilot tables in `results/`. The experiment runner writes `experiment_*.csv` and uses temporary databases; the full run can take a few minutes. `--seeds 5` is available for a shorter exploratory run and overwrites experiment summaries with that run's sample size.

Read [report.md](report.md) for methods, metric definitions, limitations and verified sources; [docs/explained.md](docs/explained.md) for the beginner walkthrough; and [results/results.md](results/results.md) for generated pilot tables.

Rule flag rates differ from actual error rates. All non-key fields are measured, extra/lost records are reported, and quarantine does not count as successful restoration. No real student data is used.
