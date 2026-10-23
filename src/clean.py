"""Apply data-quality remediation to the dirty database.

Steps (each logged with a count):
  1. standardise names, emails, dates and coded values against reference lists
  2. detect and merge duplicate students (survivorship: keep lowest id, fill gaps from the duplicate)
  3. infer missing programme from the student's enrolled courses
  4. null out invalid grades; quarantine orphan and temporally impossible enrolments
  5. queue suspected outdated records for human verification

Writes ../data/cleaned.sqlite (students, courses, enrolments, quarantine, review_queue) and ../results/cleaning_log.csv
"""
import sqlite3
from pathlib import Path

import pandas as pd

from checks import COUNTRIES, EMAIL_RE, REF_YEAR, duplicate_pairs, load, parse_date

ROOT = Path(__file__).resolve().parent.parent
DOMAIN = "uni.example.ac.uk"

PROGRAMME_MAP = {"cs": "CS", "comp sci": "CS", "computer science": "CS",
                 "is": "IS", "i.s.": "IS", "info systems": "IS", "information systems": "IS",
                 "bus": "BUS", "business": "BUS", "math": "MATH", "maths": "MATH", "mth": "MATH",
                 "psy": "PSY", "psych": "PSY", "law": "LAW", "eng": "ENG", "eng.": "ENG", "engineering": "ENG",
                 "bio": "BIO", "biology": "BIO"}
GENDER_MAP = {"f": "F", "female": "F", "m": "M", "male": "M", "x": "X", "other": "X", "non-binary": "X"}
COUNTRY_MAP = {"uk": "United Kingdom", "u.k.": "United Kingdom", "england": "United Kingdom",
               "ie": "Ireland", "eire": "Ireland", "fr": "France", "ng": "Nigeria", "in": "India",
               "ma": "Morocco", "maroc": "Morocco", "cn": "China", "prc": "China"}
COUNTRY_MAP.update({c.lower(): c for c in COUNTRIES})


def map_code(series, mapping):
    return series.map(lambda v: mapping.get(str(v).strip().lower(), v) if pd.notna(v) else v)


def fix_email(v):
    if pd.isna(v):
        return v
    v = str(v).strip().lower()
    if "@" not in v and v.endswith(DOMAIN):  # '@' dropped on entry
        v = v[: -len(DOMAIN)] + "@" + DOMAIN
    return v


def institutional(v):
    return pd.notna(v) and bool(EMAIL_RE.match(v))


def clean(dirty_db, out_db):
    t = load(dirty_db)
    s, c, e = t["students"].copy(), t["courses"].copy(), t["enrolments"].copy()
    log = []

    def step(name, n):
        log.append({"step": name, "records_changed": int(n)})

    # 1. Standardisation
    for col in ("first_name", "last_name"):
        new = s[col].map(lambda v: " ".join(str(v).split()).title() if pd.notna(v) else v)
        step(f"standardise {col}", (new != s[col]).sum())
        s[col] = new
    new = s.email.map(fix_email)
    step("standardise/repair email", ((new != s.email) & s.email.notna()).sum())
    s["email"] = new
    new = s.dob.map(parse_date)
    step("convert dob to ISO-8601", ((new != s.dob) & s.dob.notna()).sum())
    s["dob"] = new
    for col, mp in (("programme_code", PROGRAMME_MAP), ("gender", GENDER_MAP), ("country", COUNTRY_MAP)):
        new = map_code(s[col], mp)
        step(f"map {col} to code list", ((new != s[col]) & s[col].notna()).sum())
        s[col] = new

    # 2. Duplicate detection and merge
    pairs = duplicate_pairs(s)
    s = s.set_index("student_id")
    for keep, drop in pairs:
        if drop not in s.index or keep not in s.index:
            continue
        for col in s.columns:
            k, d = s.at[keep, col], s.at[drop, col]
            if col == "email":
                if not institutional(k) and institutional(d):
                    s.at[keep, col] = d
            elif pd.isna(k) and pd.notna(d):
                s.at[keep, col] = d
        e.loc[e.student_id == drop, "student_id"] = keep
        s = s.drop(drop)
    s = s.reset_index()
    step("merge duplicate students", len(pairs))
    before = len(e)
    e = e.drop_duplicates(["student_id", "course_code", "academic_year"])
    step("drop duplicate enrolments", before - len(e))

    # 3. Infer missing programme from enrolled courses
    prog = (e.merge(c[["course_code", "programme_code"]], on="course_code")
              .groupby("student_id").programme_code.agg(lambda x: x.mode().iat[0]))
    miss = s.programme_code.isna() & s.student_id.isin(prog.index)
    s.loc[miss, "programme_code"] = s.loc[miss, "student_id"].map(prog)
    step("infer missing programme from enrolments", miss.sum())

    # 4. Invalid grades and enrolments that cannot be trusted
    g = pd.to_numeric(e.grade, errors="coerce")
    bad = e.grade.notna() & (g.isna() | (g < 0) | (g > 100))
    e.loc[bad, "grade"] = None
    step("null out-of-range grades (flag for re-entry)", bad.sum())
    m = e.merge(s[["student_id", "enrol_year"]], on="student_id", how="left")
    orphan = m.enrol_year.isna().values
    early = (m.academic_year < m.enrol_year).values
    quarantine = e[orphan | early].assign(reason=["orphan student_id" if o else "year before start"
                                                  for o, q in zip(orphan, early) if o or q])
    e = e[~(orphan | early)]
    step("quarantine orphan enrolments", orphan.sum())
    step("quarantine enrolments dated before start year", early.sum())

    # 5. Suspicion is insufficient evidence of graduation or course retirement.
    overdue = (s.status == "active") & (s.enrol_year + 3 <= REF_YEAR)
    last = e.groupby("course_code").academic_year.max()
    stale = (c.active == 1) & (c.course_code.map(last).fillna(0) < REF_YEAR - 1)
    review = [
        {"table": "students", "record_id": str(sid), "reason": "past expected completion; verify status and dates"}
        for sid in s.loc[overdue, "student_id"]
    ] + [
        {"table": "courses", "record_id": str(code), "reason": "no enrolments in two academic years; verify offering status"}
        for code in c.loc[stale, "course_code"]
    ]
    review_queue = pd.DataFrame(review, columns=["table", "record_id", "reason"])
    step("queue student status verification", overdue.sum())
    step("queue course offering verification", stale.sum())

    with sqlite3.connect(out_db) as con:
        for name, df in (("students", s), ("courses", c), ("enrolments", e), ("quarantine", quarantine), ("review_queue", review_queue)):
            df.to_sql(name, con, index=False, if_exists="replace")
    return pd.DataFrame(log)


if __name__ == "__main__":
    out = ROOT / "data" / "cleaned.sqlite"
    out.unlink(missing_ok=True)
    log = clean(ROOT / "data" / "dirty.sqlite", out)
    (ROOT / "results").mkdir(exist_ok=True)
    log.to_csv(ROOT / "results" / "cleaning_log.csv", index=False)
    print(log.to_string(index=False))
