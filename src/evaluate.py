"""Run the full experiment and measure error rates before and after cleaning.

Three measures, each for the dirty and the cleaned database:
  A. rule-based check results (what an organisation without ground truth can see)
  B. ground-truth accuracy (cell and record error rates against truth.sqlite) and fix rate per injected error type
  C. reliability of information products: KPIs a university would report, vs. the true value

Usage: python3 evaluate.py   (regenerates data, cleans it, writes ../results/*.csv and results.md)
"""
from pathlib import Path

import pandas as pd

import clean as cleaner
import generate_data
from checks import EMAIL_RE, REF_YEAR, load, run_checks

ROOT = Path(__file__).resolve().parent.parent
DATA, RES = ROOT / "data", ROOT / "results"
S_COLS = ["first_name", "last_name", "email", "dob", "gender", "programme_code", "status",
          "graduation_date", "country"]
E_COLS = ["student_id", "course_code", "academic_year", "grade"]


def same(a, b):
    if pd.isna(a) and pd.isna(b):
        return True
    if pd.isna(a) or pd.isna(b):
        return False
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def accuracy(truth, test):
    out = []
    for table, key, cols in (("students", "student_id", S_COLS), ("enrolments", "enrolment_id", E_COLS),
                             ("courses", "course_code", ["active"])):
        t = truth[table].set_index(key)
        x = test[table].drop_duplicates(key).set_index(key)
        spurious = len(test[table]) - len(test[table][test[table][key].isin(t.index)])
        lost = int((~t.index.isin(x.index)).sum())
        bad_cells, bad_records = 0, 0
        for k, row in t.iterrows():
            if k not in x.index:
                bad_cells += len(cols)
                bad_records += 1
                continue
            wrong = sum(not same(row[c], x.at[k, c]) for c in cols)
            bad_cells += wrong
            bad_records += wrong > 0
        n = len(t)
        out.append({"table": table, "true_records": n, "spurious_records": spurious, "lost_records": lost,
                    "cell_error_rate": bad_cells / (n * len(cols)),
                    "record_error_rate": (bad_records + spurious) / (n + spurious)})
    return pd.DataFrame(out)


def fix_rates(truth, cleaned, log):
    """Share of injected errors whose cell now holds the true value."""
    keys = {"students": "student_id", "enrolments": "enrolment_id", "courses": "course_code"}
    rows = []
    for r in log.itertuples():
        if r.error_type == "duplicate":
            fixed = int(r.record_id) not in set(cleaned["students"].student_id)
        else:
            df = cleaned[r.table]
            rid = r.record_id if r.table == "courses" else int(r.record_id)
            hit = df[df[keys[r.table]] == rid]
            col = "student_id" if r.error_type == "duplicate_key" else r.column
            fixed = len(hit) > 0 and same(hit.iloc[0][col], r.true_value)
        rows.append({"error_type": r.error_type, "fixed": fixed})
    f = pd.DataFrame(rows).groupby("error_type").fixed.agg(injected="size", fixed="sum")
    f["fix_rate"] = f.fixed / f.injected
    return f.reset_index().sort_values("injected", ascending=False)


def kpis(db):
    s, c, e = db["students"], db["courses"], db["enrolments"]
    g = pd.to_numeric(e.grade, errors="coerce")
    done = e.academic_year < REF_YEAR
    return {
        "Active student headcount": (s.status == "active").sum(),
        "Graduates on record": (s.status == "graduated").sum(),
        "Total student records (people)": len(s),
        "Computer Science students": (s.programme_code == "CS").sum(),
        "Students reachable by institutional email": s.email.fillna("").str.match(EMAIL_RE).sum(),
        "Courses currently offered": (c.active == 1).sum(),
        "Mean grade (completed modules)": round(g[done].mean(), 2),
        "Pass rate (grade >= 40)": round((g[done & g.notna()] >= 40).mean(), 4),
        "Mean modules per student": round(e.groupby("student_id").size().mean(), 2),
    }


def md(df, floatfmt="{:.1%}"):
    df = df.copy()
    for col in df.columns:
        if df[col].dtype.kind == "f":
            df[col] = df[col].map(lambda v: floatfmt.format(v))
    head = "| " + " | ".join(map(str, df.columns)) + " |"
    sep = "|" + "|".join("---" for _ in df.columns) + "|"
    return "\n".join([head, sep] + ["| " + " | ".join(map(str, r)) + " |" for r in df.values])


def main():
    generate_data.main()
    (DATA / "cleaned.sqlite").unlink(missing_ok=True)
    RES.mkdir(exist_ok=True)
    clog = cleaner.clean(DATA / "dirty.sqlite", DATA / "cleaned.sqlite")
    clog.to_csv(RES / "cleaning_log.csv", index=False)

    truth, dirty, cleaned = (load(DATA / f"{n}.sqlite") for n in ("truth", "dirty", "cleaned"))
    log = pd.read_csv(DATA / "injection_log.csv")

    rb, recb = run_checks(DATA / "dirty.sqlite")
    ra, reca = run_checks(DATA / "cleaned.sqlite")
    rules = rb[["dimension", "rule", "table", "violations", "rate"]].rename(
        columns={"violations": "before", "rate": "rate_before"})
    rules["after"], rules["rate_after"] = ra.violations.values, ra.rate.values
    rules.to_csv(RES / "rule_checks.csv", index=False)
    dims = rules.groupby("dimension")[["before", "after"]].sum().reset_index()
    dims["reduction"] = 1 - dims.after / dims.before
    records = recb.merge(reca, on="table", suffixes=("_before", "_after"))
    records.to_csv(RES / "record_flags.csv", index=False)

    acc = accuracy(truth, dirty).merge(accuracy(truth, cleaned), on=["table", "true_records"],
                                       suffixes=("_dirty", "_cleaned"))
    acc.to_csv(RES / "accuracy_vs_truth.csv", index=False)
    fixes = fix_rates(truth, cleaned, log)
    fixes.to_csv(RES / "fix_rate_by_error_type.csv", index=False)

    kt, kd, kc = kpis(truth), kpis(dirty), kpis(cleaned)
    k = pd.DataFrame({"KPI": list(kt), "truth": list(kt.values()), "dirty": list(kd.values()),
                      "cleaned": list(kc.values())})
    k["error_dirty"] = (k.dirty - k.truth).abs() / k.truth
    k["error_cleaned"] = (k.cleaned - k.truth).abs() / k.truth
    k.to_csv(RES / "kpi_reliability.csv", index=False)

    report = [
        "# Experiment results", "",
        "Generated by `src/evaluate.py`. Rates are shares of the records checked.", "",
        "## A. Rule violations by dimension", "", md(dims), "",
        "## A2. Rule violations by rule", "",
        md(rules.drop(columns=["rate_before", "rate_after"])), "",
        "## A3. Records flagged by at least one rule", "", md(records), "",
        "## B. Accuracy against ground truth", "", md(acc), "",
        "## B2. Fix rate by injected error type", "", md(fixes), "",
        "## C. Reliability of reported KPIs", "",
        md(k.assign(truth=k.truth.astype(str), dirty=k.dirty.astype(str), cleaned=k.cleaned.astype(str))), "",
        "## Cleaning actions", "", md(clog), "",
    ]
    (RES / "results.md").write_text("\n".join(report))
    print("\n".join(report))


if __name__ == "__main__":
    main()
