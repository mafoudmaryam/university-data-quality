# Data Quality and Information Management: How Poor-Quality Data Affects the Reliability of a University Information System

*Research plan, pilot experiment and governance review. Draft v1, October 2026.*

## 1. Research plan

### 1.1 Research question

**How does poor-quality data affect the reliability of information systems?**

Sub-questions, answered here for a university student-records system:

1. **RQ1.** How much do duplicate, incomplete, outdated and inconsistent records distort the information a university reports (headcounts, grades, programme sizes)?
2. **RQ2.** How much do rule-based data-quality checks and cleaning reduce error rates, and which error types do they fail to fix?
3. **RQ3.** What do established governance frameworks (DAMA-DMBOK, ISO 8000, ISO/IEC 25012) recommend to prevent these errors in the first place?

### 1.2 Hypotheses

| # | Hypothesis | Result in pilot |
|---|---|---|
| H1 | Small cell-level error rates (under 10%) produce much larger distortions in reported KPIs. | **Supported.** A 7.8% student cell-error rate inflated active headcount by 29%. |
| H2 | Automated checks and cleaning reduce rule violations by more than 80%. | **Supported for 4 of 5 dimensions** (Uniqueness, Validity, Consistency, Timeliness all 99.8–100%). Completeness only 5%. |
| H3 | Format and coding errors are fully fixable, but missing values and broken references are not fixable without going back to the source. | **Supported.** Codes, formats and outdated statuses were 100% fixed. Missing values 10%, orphan and impossible enrolments 0% (they were quarantined). |
| H4 | Errors in master data (students) spread to the data that depends on it (enrolments, grades, KPIs). | **Supported.** Duplicate students split enrolment histories, so mean modules per student fell from 5.08 to 4.63. |

### 1.3 Method

A controlled experiment on synthetic data, so the *true* value of every record is known:

1. **Ground truth.** Generate a clean university database of students, courses and enrolments (`src/generate_data.py`).
2. **Error injection.** Copy it and inject known errors at realistic rates. Every injected error is logged (`data/injection_log.csv`).
3. **Data profiling and rule checks.** Run 19 rules grouped by quality dimension (`src/checks.py`).
4. **Cleaning.** Standardise values, link and merge duplicates, infer missing values, quarantine untrustworthy records, and refresh outdated ones (`src/clean.py`).
5. **Measurement** (`src/evaluate.py`), at three levels:
   - **A. Rule violations** before and after cleaning. This is what an organisation can see without ground truth.
   - **B. Accuracy against ground truth**: cell and record error rates, plus the fix rate for each error type.
   - **C. Information reliability**: nine KPIs a university would report, compared with their true values.
6. **Literature and governance review** (Section 4).

Tools: Python 3, pandas, SQLite. The run is deterministic (seed 42), and `python3 src/evaluate.py` reproduces everything.

## 2. Dataset

| Table | True records | Key fields |
|---|---|---|
| students | 1,000 | id, name, email, date of birth, gender, programme, enrol year, status, graduation date, country |
| courses | 56 (8 programmes × 7) | code, title, programme, credits, active, retired year |
| enrolments | 5,084 | student, course, academic year, grade (0–100; empty for the current year) |

**Injected errors (1,248 in total):**

| Problem type | How it was injected | Count |
|---|---|---|
| Duplicate | 5% of students re-entered under a new ID, with changed letter case, extra spaces, swapped letters or a personal email. Half of each student's enrolments moved to the duplicate ID. | 50 records, 131 enrolments moved |
| Incomplete | Missing email (6%), date of birth (4%), programme (3%) and grade (5% of completed modules) | 349 cells |
| Outdated | 15% of graduates still marked "active", and 3 retired courses still listed as offered | 181 cells |
| Inconsistent | Programme name variants ("Comp Sci", "cs"), mixed date formats, gender and country variants ("UK", "U.K.", "England") | 374 cells |
| Invalid | Email without "@" (2%), grades out of range such as 105, −5 or 999 (1%) | 61 cells |
| Integrity | Enrolments that point to students who do not exist (1%), and enrolments dated before the student started (1%) | 102 rows |

## 3. Results

Full tables are in [results/results.md](results/results.md) and the CSV files in `results/`.

### 3.1 Profiling: rule violations by dimension (measure A)

| Dimension | Violations before | After | Reduction |
|---|---|---|---|
| Uniqueness | 69 | 0 | 100% |
| Validity | 465 | 1 | 99.8% |
| Consistency (integrity) | 90 | 0 | 100% |
| Timeliness | 92 | 0 | 100% |
| Completeness | 376 | 357 | 5.1% |

The share of student records failing at least one rule fell from **51.7% to 9.8%**. All 19 rules return zero violations on the ground-truth data, so the rules produced no false alarms.

### 3.2 Accuracy against ground truth (measure B)

| Table | Cell error rate, dirty → cleaned | Record error rate, dirty → cleaned |
|---|---|---|
| students | 7.8% → **1.1%** | 51.4% → **9.8%** |
| enrolments | 2.4% → 3.2% | 9.3% → **7.2%** |
| courses | 5.4% → **0.0%** | 5.4% → **0.0%** |

**Fix rate by error type:** inconsistent codes 100%, inconsistent formats 100%, outdated 100%, duplicates 94% (47 of 50), moved enrolments 89%, invalid values 31%, missing values 10%, orphan and impossible enrolments 0%.

The cell error rate for enrolments *rose*. Quarantining 92 untrustworthy enrolments removes bad rows from reports, but it also leaves real enrolments missing. This is an important trade-off. Cleaning can make a dataset *trustworthy* without making it *complete*. The only way to recover those rows is to fix them at the source, such as the department's records or the student.

### 3.3 Reliability of reported information (measure C)

| KPI | Truth | Dirty (error) | Cleaned (error) |
|---|---|---|---|
| Active student headcount | 345 | 445 (**29.0%**) | 345 (0.0%) |
| Graduates on record | 594 | 541 (8.9%) | 597 (0.5%) |
| Distinct students | 1,000 | 1,050 (5.0%) | 1,003 (0.3%) |
| Computer Science students | 131 | 124 (5.3%) | 131 (0.0%) |
| Students reachable by university email | 1,000 | 921 (7.9%) | 942 (5.8%) |
| Courses currently offered | 53 | 56 (5.7%) | 53 (0.0%) |
| Mean grade, completed modules | 61.65 | 64.41 (4.5%) | 61.70 (0.1%) |
| Pass rate | 97.2% | 96.9% (0.3%) | 97.1% (0.1%) |
| Mean modules per student | 5.08 | 4.63 (8.9%) | 4.98 (2.0%) |

### 3.4 Interpretation

- **Small errors are amplified (H1).** Only about 9% of student records were outdated, yet the active headcount was overstated by 29%. Headcount drives funding, timetabling and accommodation planning. The amplification happens because the outdated records all pile into one small category ("active").
- **A few extreme values distort averages.** Just 42 invalid grades (1%) moved the mean grade by almost three points.
- **Errors propagate (H4).** Duplicate student records split enrolment histories. That would break progression checks, transcripts and degree classification.
- **Rule checks cannot see what is missing.** Completeness is the dimension cleaning helps least. Programme could be inferred from enrolments, but grades, emails and dates of birth could not be reliably recreated. Prevention matters more here: required fields at the point of entry and validation in the source system.
- **Fuzzy duplicate matching has limits.** Three duplicates were missed. In each one, the original record had no date of birth (the matching key), and the duplicate had either a personal email or no email at all. Combining several matching keys and adding a human review queue would close this gap (Fellegi & Sunter, 1969).

### 3.5 Threats to validity

- The data is synthetic, and the error rates were chosen by the researcher, not measured in a real system. *Next step:* calibrate the rates against published audits or an anonymised extract.
- The same rules were used to inject, detect and clean the errors, which favours high fix rates. *Next step:* have a second person inject "unseen" error types, as a blind test.
- Only one random seed was used. *Next step:* run 30 seeds and report means with confidence intervals.

## 4. Review of data-governance practices

| Framework | What it contributes | How it applies here |
|---|---|---|
| **DAMA-DMBOK 2** (DAMA International, 2017) | Treats data quality as one of 11 knowledge areas under data governance. Defines roles (data owner, data steward), quality dimensions (completeness, uniqueness, timeliness, validity, accuracy, consistency) and a plan–do–check–act improvement cycle. | The rules in `checks.py` follow the DAMA dimensions. Stewardship decides who fixes quarantined records. |
| **ISO 8000** (ISO 8000-1:2022; ISO 8000-8:2015; ISO 8000-61:2016) | International standard for data and information quality. Part 8 covers syntactic, semantic and pragmatic quality and how to measure it. Part 61 gives a process reference model for data-quality management (planning, control, assurance, improvement). | Code lists and ISO-8601 dates support syntactic and semantic quality. The repeatable `evaluate.py` run matches the "data quality control" process. |
| **ISO/IEC 25012:2008** (SQuaRE data quality model) | Defines 15 data-quality characteristics. Some are inherent to the data (accuracy, completeness, consistency, credibility, currentness); others depend on the system (availability, recoverability, and so on). | Provides the vocabulary for the error-rate metrics. "Currentness" here means outdated statuses. |
| **Wang & Strong (1996)** | Found, from the point of view of data *consumers*, that data quality is "fitness for use" across intrinsic, contextual, representational and accessibility categories. | Justifies measuring KPIs (measure C) rather than only cell accuracy. |
| **Pipino, Lee & Wang (2002); Batini et al. (2009)** | Methods for objective metrics, such as simple ratios, and for structured assessment-and-improvement methodologies. | The violation-rate and fix-rate metrics are "simple ratio" metrics. |
| **Khatri & Brown (2010)** | Data-governance design: decision areas (principles, quality, metadata, access, lifecycle) and who has decision rights over each. | Supports the recommendation of a named owner for student master data. |
| **Regulatory context** | GDPR Article 5(1)(d) requires personal data to be "accurate and, where necessary, kept up to date". UK universities also submit student data to HESA (Data Futures), so quality errors become reporting errors to regulators. | Outdated statuses and duplicates are a compliance risk, not just an analytics problem. |
| **Cost evidence** | Redman (1998, 2016) and Gartner (2021) estimate large organisational costs from poor data (Gartner gives an average of US$12.9m per organisation per year). | Motivates the research. The headcount distortion found here is a concrete example. |

**Recommendations for a university, drawn from these frameworks and the pilot:**

1. Assign a **data owner and data stewards** for student master data (DAMA).
2. **Validate at entry.** Enforce required fields, code lists and date formats in the source system, because missing data could barely be repaired afterwards.
3. Use **one person identifier** across systems, with duplicate checks when a record is created.
4. Trigger **status changes from events**, such as an exam board decision setting "graduated", instead of relying on manual updates. This prevents outdated records.
5. **Monitor continuously.** Run the rule set on a schedule, and track violation rates by dimension on a dashboard (ISO 8000-61 "control").
6. Keep a **quarantine and remediation workflow** so excluded records are fixed at the source, not silently dropped.

## 5. Next steps

1. Run the experiment on several seeds and error rates, for example 1–20%, to draw a curve of KPI error against injected error rate.
2. Compare duplicate-matching methods (exact, fuzzy, probabilistic Fellegi–Sunter) using precision and recall.
3. Add SQL constraints (`NOT NULL`, `CHECK`, `FOREIGN KEY`) in SQLite to compare *prevention* with *cleaning*.
4. Write up the literature review in full, checking page references.

## 6. Repository layout and how to rerun

```
data-quality-research/
  report.md                 this document
  src/generate_data.py      ground truth + error injection
  src/checks.py             19 data-quality rules by dimension
  src/clean.py              cleaning and remediation pipeline
  src/evaluate.py           runs everything and writes results/
  data/                     truth.sqlite, dirty.sqlite, cleaned.sqlite, dirty_*.csv, injection_log.csv
  results/                  results.md and CSVs (rule_checks, accuracy_vs_truth, fix_rate_by_error_type, kpi_reliability, cleaning_log)
```

Run `cd src && python3 evaluate.py`. It needs Python 3 and pandas.

## References

- Batini, C., Cappiello, C., Francalanci, C., & Maurino, A. (2009). Methodologies for data quality assessment and improvement. *ACM Computing Surveys, 41*(3), 1–52.
- DAMA International. (2017). *DAMA-DMBOK: Data Management Body of Knowledge* (2nd ed.). Technics Publications.
- European Union. (2016). General Data Protection Regulation (EU) 2016/679, Article 5(1)(d).
- Fellegi, I. P., & Sunter, A. B. (1969). A theory for record linkage. *Journal of the American Statistical Association, 64*(328), 1183–1210.
- Gartner. (2021). *How to Improve Your Data Quality*. Gartner, Inc.
- ISO. (2015). *ISO 8000-8: Data quality — Part 8: Information and data quality: Concepts and measuring*.
- ISO. (2016). *ISO 8000-61: Data quality — Part 61: Data quality management: Process reference model*.
- ISO. (2022). *ISO 8000-1: Data quality — Part 1: Overview*.
- ISO/IEC. (2008). *ISO/IEC 25012: Software engineering — SQuaRE — Data quality model*.
- Khatri, V., & Brown, C. V. (2010). Designing data governance. *Communications of the ACM, 53*(1), 148–152.
- Pipino, L. L., Lee, Y. W., & Wang, R. Y. (2002). Data quality assessment. *Communications of the ACM, 45*(4), 211–218.
- Redman, T. C. (1998). The impact of poor data quality on the typical enterprise. *Communications of the ACM, 41*(2), 79–82.
- Redman, T. C. (2016). Bad data costs the U.S. $3 trillion per year. *Harvard Business Review*.
- Wang, R. Y., & Strong, D. M. (1996). Beyond accuracy: What data quality means to data consumers. *Journal of Management Information Systems, 12*(4), 5–33.

*References were cited from the author's knowledge and not retrieved during drafting. Check editions and page numbers before submission.*
