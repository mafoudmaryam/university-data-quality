"""Generate a synthetic university dataset (ground truth) and a corrupted copy.

Outputs (in ../data):
  truth.sqlite        clean reference data (students, courses, enrolments)
  dirty.sqlite        the same data with injected quality problems
  injection_log.csv   one row per injected error (table, record, column, type, true, dirty)

Reference date for the dataset is 2026-10-01 (start of academic year 2026/27).
Programmes are three years long; enrolments are recorded per academic year.
"""
import csv
import random
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_STUDENTS = 1000
REF_YEAR = 2026
DATA = Path(__file__).resolve().parent.parent / "data"

FIRST = ["Amira", "James", "Sofia", "Omar", "Emily", "Yusuf", "Chloe", "Liam", "Fatima", "Noah",
         "Hannah", "Adam", "Zara", "Lucas", "Maya", "Ethan", "Layla", "Daniel", "Aisha", "Oliver",
         "Grace", "Hassan", "Isla", "Ryan", "Leila", "Samuel", "Nadia", "Jacob", "Mariam", "Leo"]
LAST = ["Smith", "Khan", "Jones", "Ahmed", "Brown", "Ali", "Taylor", "Patel", "Wilson", "Hussain",
        "Evans", "Mafoud", "Thomas", "Begum", "Roberts", "Chen", "Walker", "Nguyen", "Wright", "Haddad",
        "Green", "Ibrahim", "Hall", "Rahman", "Wood", "Kowalski", "Clarke", "Silva", "Hughes", "Mensah"]
PROGRAMMES = {"CS": "Computer Science", "IS": "Information Systems", "BUS": "Business",
              "MATH": "Mathematics", "PSY": "Psychology", "LAW": "Law", "ENG": "Engineering", "BIO": "Biology"}
COUNTRIES = ["United Kingdom"] * 6 + ["Ireland", "France", "Nigeria", "India", "Morocco", "China"]
DOMAIN = "uni.example.ac.uk"


def make_truth(rng: random.Random):
    # Courses: 7 per programme, 3 of which were retired before 2024/25
    courses = []
    for code in PROGRAMMES:
        for i in range(1, 8):
            courses.append({"course_code": f"{code}{100 + i}", "title": f"{PROGRAMMES[code]} module {i}",
                            "programme_code": code, "credits": rng.choice([15, 15, 30]),
                            "active": 1, "retired_year": None})
    courses = pd.DataFrame(courses)
    retired = courses.sample(3, random_state=SEED).index
    courses.loc[retired, "active"] = 0
    courses.loc[retired, "retired_year"] = 2023

    students, used_emails = [], set()
    for sid in range(1, N_STUDENTS + 1):
        fn, ln = rng.choice(FIRST), rng.choice(LAST)
        base = f"{fn.lower()}.{ln.lower()}"
        email, n = f"{base}@{DOMAIN}", 1
        while email in used_emails:
            n += 1
            email = f"{base}{n}@{DOMAIN}"
        used_emails.add(email)
        enrol_year = rng.randint(2019, REF_YEAR)
        dob = pd.Timestamp(enrol_year - 18 - rng.choice([0, 0, 0, 1, 2, 5]), rng.randint(1, 12), rng.randint(1, 28))
        withdrawn = rng.random() < 0.06
        if withdrawn:
            status, grad = "withdrawn", None
        elif enrol_year + 3 <= REF_YEAR:
            status, grad = "graduated", f"{enrol_year + 3}-06-30"
        else:
            status, grad = "active", None
        students.append({"student_id": sid, "first_name": fn, "last_name": ln, "email": email,
                         "dob": dob.strftime("%Y-%m-%d"), "gender": rng.choice(["F", "M", "F", "M", "X"]),
                         "programme_code": rng.choice(list(PROGRAMMES)), "enrol_year": enrol_year,
                         "status": status, "graduation_date": grad, "country": rng.choice(COUNTRIES),
                         "last_updated": f"{min(enrol_year + 3, REF_YEAR)}-09-15" if status != "withdrawn"
                         else f"{enrol_year + 1}-01-10"})
    students = pd.DataFrame(students)

    enrolments, eid = [], 1
    for s in students.itertuples():
        last = s.enrol_year if s.status == "withdrawn" else min(s.enrol_year + 2, REF_YEAR)
        for year in range(s.enrol_year, last + 1):
            pool = courses[(courses.programme_code == s.programme_code) &
                           ((courses.active == 1) | (courses.retired_year > year))]
            for c in pool.sample(min(2, len(pool)), random_state=rng.randint(0, 10**6)).course_code:
                grade = None if year == REF_YEAR else int(np.clip(rng.gauss(62, 12), 0, 100))
                enrolments.append({"enrolment_id": eid, "student_id": s.student_id, "course_code": c,
                                   "academic_year": year, "grade": grade})
                eid += 1
    return students, courses, pd.DataFrame(enrolments)


def corrupt(students, courses, enrolments, rng: random.Random, *, scale=1.0, error_types=None):
    """Scale baseline injection probabilities; optionally isolate an error family.

    Duplicate-key changes belong to the duplicate family. Rates are capped at 1.
    """
    if scale < 0:
        raise ValueError("scale must be nonnegative")
    enabled = set(error_types) if error_types is not None else {
        "duplicate", "missing", "outdated", "inconsistent_code",
        "inconsistent_format", "invalid", "orphan_fk", "inconsistent_temporal"}
    s, c, e = students.copy(), courses.copy(), enrolments.copy()
    for df in (s, c, e):
        for col in df.columns:
            df[col] = df[col].astype(object)
    log = []

    def note(table, rid, col, etype, true, dirty):
        log.append({"table": table, "record_id": rid, "column": col, "error_type": etype,
                    "true_value": true, "dirty_value": dirty})

    def pick(df, frac, where=None, *, family):
        if family not in enabled:
            return []
        frac = min(1.0, frac * scale)
        pool = df if where is None else df[where]
        return list(pool.sample(frac=frac, random_state=rng.randint(0, 10**6)).index) if len(pool) else []

    # 1. DUPLICATES: re-keyed copies of 5% of students, with spelling/format variations
    dup_rows, next_id = [], N_STUDENTS + 1
    for i in pick(s, 0.05, family="duplicate"):
        orig = s.loc[i].copy()
        d = orig.copy()
        d["student_id"] = next_id
        variant = rng.choice(["case", "space", "typo", "email"])
        if variant == "case":
            d["first_name"], d["last_name"] = orig.first_name.upper(), orig.last_name.upper()
        elif variant == "space":
            d["first_name"] = f" {orig.first_name}  "
        elif variant == "typo" and len(orig.last_name) > 3:
            ln = list(orig.last_name)
            ln[1], ln[2] = ln[2], ln[1]
            d["last_name"] = "".join(ln)
        d["email"] = rng.choice([orig.email.upper(), f"{orig.first_name.lower()}{rng.randint(1, 99)}@gmail.com", None])
        dup_rows.append(d)
        note("students", next_id, "*", "duplicate", int(orig.student_id), next_id)
        # move part of the original's enrolment history onto the duplicate key
        mine = e.index[e.student_id == orig.student_id]
        for j in mine[::2]:
            note("enrolments", int(e.at[j, "enrolment_id"]), "student_id", "duplicate_key",
                 int(orig.student_id), next_id)
            e.at[j, "student_id"] = next_id
        next_id += 1
    s = pd.concat([s, pd.DataFrame(dup_rows)], ignore_index=True)
    originals = s.student_id <= N_STUDENTS

    # 2. MISSING VALUES
    for col, frac in [("email", 0.06), ("dob", 0.04), ("programme_code", 0.03)]:
        for i in pick(s, frac, originals & s[col].notna(), family="missing"):
            note("students", int(s.at[i, "student_id"]), col, "missing", s.at[i, col], None)
            s.at[i, col] = None
    for i in pick(e, 0.05, e.grade.notna(), family="missing"):
        note("enrolments", int(e.at[i, "enrolment_id"]), "grade", "missing", e.at[i, "grade"], None)
        e.at[i, "grade"] = None

    # 3. OUTDATED RECORDS: graduates never updated, retired courses still listed
    for i in pick(s, 0.15, originals & (s.status == "graduated"), family="outdated"):
        sid = int(s.at[i, "student_id"])
        note("students", sid, "status", "outdated", "graduated", "active")
        note("students", sid, "graduation_date", "outdated", s.at[i, "graduation_date"], None)
        s.at[i, "status"], s.at[i, "graduation_date"] = "active", None
        old_update = s.at[i, "last_updated"]
        new_update = f"{s.at[i, 'enrol_year']}-09-15"
        note("students", sid, "last_updated", "outdated", old_update, new_update)
        s.at[i, "last_updated"] = new_update
    for i in pick(c, 1.0, c.active == 0, family="outdated"):
        note("courses", c.at[i, "course_code"], "active", "outdated", 0, 1)
        c.at[i, "active"] = 1

    # 4. INCONSISTENT / INVALID VALUES
    prog_variants = {"CS": ["cs", "Comp Sci", "Computer Science"], "IS": ["I.S.", "Info Systems", "is"],
                     "BUS": ["Business", "bus "], "MATH": ["Maths", "MTH"], "PSY": ["Psych", "psy"],
                     "LAW": ["Law", "law"], "ENG": ["Eng.", "Engineering"], "BIO": ["Biology", "bio"]}
    for i in pick(s, 0.08, originals & s.programme_code.notna(), family="inconsistent_code"):
        v = rng.choice(prog_variants[s.at[i, "programme_code"]])
        note("students", int(s.at[i, "student_id"]), "programme_code", "inconsistent_code", s.at[i, "programme_code"], v)
        s.at[i, "programme_code"] = v
    for i in pick(s, 0.10, originals & s.dob.notna(), family="inconsistent_format"):
        v = pd.Timestamp(s.at[i, "dob"]).strftime(rng.choice(["%d/%m/%Y", "%m-%d-%Y", "%d %b %Y"]))
        note("students", int(s.at[i, "student_id"]), "dob", "inconsistent_format", s.at[i, "dob"], v)
        s.at[i, "dob"] = v
    gmap = {"F": ["female", "f", "Female"], "M": ["male", "m", "Male"], "X": ["other", "non-binary"]}
    for i in pick(s, 0.10, originals, family="inconsistent_code"):
        v = rng.choice(gmap[s.at[i, "gender"]])
        note("students", int(s.at[i, "student_id"]), "gender", "inconsistent_code", s.at[i, "gender"], v)
        s.at[i, "gender"] = v
    cmap = {"United Kingdom": ["UK", "U.K.", "England", "united kingdom"], "Ireland": ["IE", "Eire"],
            "France": ["FR", "france"], "Nigeria": ["NG"], "India": ["IN", "india"], "Morocco": ["MA", "Maroc"],
            "China": ["CN", "PRC"]}
    for i in pick(s, 0.10, originals, family="inconsistent_code"):
        v = rng.choice(cmap[s.at[i, "country"]])
        note("students", int(s.at[i, "student_id"]), "country", "inconsistent_code", s.at[i, "country"], v)
        s.at[i, "country"] = v
    for i in pick(s, 0.02, originals & s.email.notna(), family="invalid"):
        v = s.at[i, "email"].replace("@", "")
        note("students", int(s.at[i, "student_id"]), "email", "invalid", s.at[i, "email"], v)
        s.at[i, "email"] = v
    for i in pick(e, 0.01, e.grade.notna(), family="invalid"):
        v = rng.choice([105, 110, -5, 999])
        note("enrolments", int(e.at[i, "enrolment_id"]), "grade", "invalid", e.at[i, "grade"], v)
        e.at[i, "grade"] = v
    # orphan enrolments (student key does not exist) and impossible years (before student enrolled)
    for i in pick(e, 0.01, family="orphan_fk"):
        v = int(rng.randint(5000, 5999))
        note("enrolments", int(e.at[i, "enrolment_id"]), "student_id", "orphan_fk", int(e.at[i, "student_id"]), v)
        e.at[i, "student_id"] = v
    for i in pick(e, 0.01, family="inconsistent_temporal"):
        v = int(e.at[i, "academic_year"]) - rng.randint(2, 4)
        note("enrolments", int(e.at[i, "enrolment_id"]), "academic_year", "inconsistent_temporal",
             int(e.at[i, "academic_year"]), v)
        e.at[i, "academic_year"] = v

    s = s.sample(frac=1, random_state=SEED).reset_index(drop=True)  # shuffle so duplicates are not at the end
    return s, c, e, pd.DataFrame(log)


def save(path, **tables):
    path.unlink(missing_ok=True)
    with sqlite3.connect(path) as con:
        for name, df in tables.items():
            df.to_sql(name, con, index=False)


def main():
    rng = random.Random(SEED)
    DATA.mkdir(exist_ok=True)
    students, courses, enrolments = make_truth(rng)
    ds, dc, de, log = corrupt(students, courses, enrolments, rng)
    save(DATA / "truth.sqlite", students=students, courses=courses, enrolments=enrolments)
    save(DATA / "dirty.sqlite", students=ds, courses=dc, enrolments=de)
    log.to_csv(DATA / "injection_log.csv", index=False, quoting=csv.QUOTE_NONNUMERIC)
    for name, df in [("students", ds), ("courses", dc), ("enrolments", de)]:
        df.to_csv(DATA / f"dirty_{name}.csv", index=False)
    print(f"truth: {len(students)} students, {len(courses)} courses, {len(enrolments)} enrolments")
    print(f"dirty: {len(ds)} students, {len(dc)} courses, {len(de)} enrolments")
    print(log.error_type.value_counts().to_string())


if __name__ == "__main__":
    main()
