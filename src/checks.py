"""Rule-based data-quality checks, grouped by DAMA / ISO 25012 quality dimension.

run_checks(db_path) -> DataFrame with one row per rule:
  dimension, rule, table, violations, checked, rate
plus flagged record ids per table for record-level error rates.
"""
import re
import sqlite3
from difflib import SequenceMatcher

import pandas as pd

REF_YEAR = 2026
PROGRAMMES = {"CS", "IS", "BUS", "MATH", "PSY", "LAW", "ENG", "BIO"}
COUNTRIES = {"United Kingdom", "Ireland", "France", "Nigeria", "India", "Morocco", "China"}
GENDERS = {"F", "M", "X"}
EMAIL_RE = re.compile(r"^[a-z0-9.]+@uni\.example\.ac\.uk$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load(db_path):
    with sqlite3.connect(db_path) as con:
        return {t: pd.read_sql(f"SELECT * FROM {t}", con) for t in ("students", "courses", "enrolments")}


def norm_name(x):
    return " ".join(str(x).split()).lower() if pd.notna(x) else ""


def parse_date(x):
    """Parse the date formats seen in the source systems; None when unparseable."""
    if pd.isna(x):
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m-%d-%Y", "%d %b %Y"):
        try:
            return pd.to_datetime(x, format=fmt).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass
    return None


def duplicate_pairs(students, threshold=0.85):
    """Probable duplicate student records: block on date of birth + enrol year, then fuzzy-match full name;
    also treat a shared email address as the same person.

    Returns list of (keep_id, drop_id) with the lower id kept.
    """
    s = students.assign(_dob=students.dob.map(parse_date),
                        _name=(students.first_name.map(norm_name) + " " + students.last_name.map(norm_name)))
    pairs = []
    for _, block in s[s._dob.notna()].groupby(["_dob", "enrol_year"]):
        rows = block.sort_values("student_id").to_dict("records")
        for i, a in enumerate(rows):
            for b in rows[i + 1:]:
                if SequenceMatcher(None, a["_name"], b["_name"]).ratio() >= threshold:
                    pairs.append((int(a["student_id"]), int(b["student_id"])))
    # second pass: same (case-insensitive) email is the same person
    s["_email"] = s.email.str.strip().str.lower()
    for _, block in s[s._email.notna()].groupby("_email"):
        ids = sorted(block.student_id)
        pairs += [(int(ids[0]), int(d)) for d in ids[1:]]
    return sorted(set(pairs))


def run_checks(db_path):
    t = load(db_path)
    s, c, e = t["students"], t["courses"], t["enrolments"]
    results, flagged = [], {"students": set(), "courses": set(), "enrolments": set()}

    def rule(dimension, name, table, mask, checked, key):
        df = {"students": s, "courses": c, "enrolments": e}[table]
        ids = set(df.loc[mask, key])
        flagged[table] |= ids
        results.append({"dimension": dimension, "rule": name, "table": table,
                        "violations": int(mask.sum()), "checked": int(checked)})

    # Completeness
    for col in ("email", "dob", "programme_code"):
        rule("Completeness", f"student {col} is missing", "students", s[col].isna(), len(s), "student_id")
    past = e.academic_year < REF_YEAR
    rule("Completeness", "grade missing for a completed year", "enrolments", past & e.grade.isna(), past.sum(), "enrolment_id")

    # Uniqueness
    em = s.email.str.lower().str.strip()
    rule("Uniqueness", "email shared by >1 student", "students", em.notna() & em.duplicated(keep=False), len(s), "student_id")
    dup_ids = {d for _, d in duplicate_pairs(s)}
    rule("Uniqueness", "probable duplicate person (dob + fuzzy name)", "students", s.student_id.isin(dup_ids), len(s), "student_id")
    rule("Uniqueness", "same student/course/year enrolled twice", "enrolments",
         e.duplicated(["student_id", "course_code", "academic_year"], keep="first"), len(e), "enrolment_id")

    # Validity (conformance to format / reference data)
    rule("Validity", "email not in institutional format", "students",
         s.email.notna() & ~s.email.fillna("").str.match(EMAIL_RE), s.email.notna().sum(), "student_id")
    rule("Validity", "dob not ISO-8601 (YYYY-MM-DD)", "students",
         s.dob.notna() & ~s.dob.fillna("").str.match(ISO_DATE_RE), s.dob.notna().sum(), "student_id")
    rule("Validity", "gender not in code list", "students", ~s.gender.isin(GENDERS), len(s), "student_id")
    rule("Validity", "programme not in code list", "students",
         s.programme_code.notna() & ~s.programme_code.isin(PROGRAMMES), s.programme_code.notna().sum(), "student_id")
    rule("Validity", "country not in code list", "students", ~s.country.isin(COUNTRIES), len(s), "student_id")
    g = pd.to_numeric(e.grade, errors="coerce")
    rule("Validity", "grade outside 0-100", "enrolments", g.notna() & ((g < 0) | (g > 100)), g.notna().sum(), "enrolment_id")

    # Consistency / referential integrity
    rule("Consistency", "enrolment references unknown student", "enrolments",
         ~e.student_id.isin(s.student_id), len(e), "enrolment_id")
    rule("Consistency", "enrolment references unknown course", "enrolments",
         ~e.course_code.isin(c.course_code), len(e), "enrolment_id")
    m = e.merge(s[["student_id", "enrol_year", "status"]], on="student_id", how="left")
    rule("Consistency", "enrolment year before student's start year", "enrolments",
         (m.academic_year < m.enrol_year).values, len(e), "enrolment_id")
    rule("Consistency", "graduated student without graduation date", "students",
         (s.status == "graduated") & s.graduation_date.isna(), (s.status == "graduated").sum(), "student_id")

    # Timeliness (currency)
    rule("Timeliness", "'active' student past expected completion", "students",
         (s.status == "active") & (s.enrol_year + 3 <= REF_YEAR), (s.status == "active").sum(), "student_id")
    recent = set(e.loc[e.academic_year >= REF_YEAR - 2, "course_code"])
    rule("Timeliness", "'active' course with no enrolments in 2 years", "courses",
         (c.active == 1) & ~c.course_code.isin(recent), (c.active == 1).sum(), "course_code")

    r = pd.DataFrame(results)
    r["rate"] = (r.violations / r.checked.where(r.checked > 0)).fillna(0)
    sizes = {"students": len(s), "courses": len(c), "enrolments": len(e)}
    records = pd.DataFrame([{"table": k, "records": sizes[k], "records_flagged": len(v),
                             "record_error_rate": len(v) / sizes[k]} for k, v in flagged.items()])
    return r, records


if __name__ == "__main__":
    import sys
    rules, records = run_checks(sys.argv[1])
    print(rules.to_string(index=False))
    print(records.to_string(index=False))
