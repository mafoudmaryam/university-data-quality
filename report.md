# Data quality and the reliability of a university information system

Author: Maryam Mafoud

## 1. Research question and scope

How do duplicate, incomplete, outdated, inconsistent and invalid records affect the accuracy of reports from a university information system, and what can automated checks and conservative cleaning improve?

Reliability here means **accuracy of reported information**. This experiment does not measure uptime, security, user satisfaction or the reliability of every university system. It is a synthetic study, not an audit of a real institution.

## 2. Experimental design

The reference university contains 1,000 fictional students, 56 courses and 5,084 enrolments in the seed-42 pilot. The reference academic year is 2026. Programme length is three years in this simulation; that assumption is not evidence of graduation in practice.

1. Generate reference data with known correct values.
2. Inject controlled errors and log changed fields, including outdated update dates.
3. Apply 19 checks for completeness, uniqueness, validity, consistency and timeliness.
4. Standardise values, merge probable duplicates, infer missing programmes from course histories, blank invalid grades and quarantine broken enrolments.
5. Queue suspected outdated students and course offerings for verification. Do not invent graduation dates or retirement decisions.
6. Measure rule flags, actual errors, detection precision/recall, duplicate-pair precision/recall and university reporting errors.

`src/evaluate.py` reproduces the pilot. `src/experiments.py` runs **55 scenarios**: 30 mixed-error seeds (42–71), eight isolated error families at multipliers 0.25, 1 and 2, and one zero-error control. For isolated scenarios, reference data and the corruption seed are fixed (42 and 10042), so the error family can be studied independently. Each isolated scenario has one seed and is exploratory.

Multipliers scale the baseline probabilities in `generate_data.py`, capped at 100%; they are **not a uniform dataset error percentage**. For example, the baseline missing-email probability is 6%, while duplicate-student probability is 5%. Retired-course corruption uses a baseline probability of 100% among retired courses and therefore saturates. Actual injection counts are saved in `experiment_scenarios.csv`.

### Measurement definitions

- **Rule flag rate:** records failing at least one rule divided by records in the working table. A flag is suspicion, not proof of an error.
- **Cell error rate:** mismatching non-key fields divided by all non-key fields in the reference table. Missing reference rows count as wrong in every evaluated field; extra rows are reported separately. Students use all 11 non-key fields, enrolments use four, and courses use five.
- **Record error rate:** wrong or missing reference records plus extra records, divided by reference records plus extras.
- **Precision:** truly erroneous flagged records divided by all flagged records. **Recall:** flagged erroneous records divided by all erroneous records present. Errors are established through semantic comparison with reference data; numeric text and numeric values compare equally. Removed records are counted as lost records, not detectable rows.
- **Duplicate-pair precision/recall:** compare predicted canonical-ID pairs with the injected duplicate relationships. These are more appropriate for duplicate matching than treating every unchanged canonical row implicated by a shared email as an error.
- **Fix rate:** logged injection events whose field matches its logged pre-injection value, or whose duplicate row was removed. Overlapping injections can affect this measure; it is not an independent causal estimate.
- **KPI error:** absolute difference from the reference KPI, divided by the absolute reference value. Pass-rate errors are relative errors, not percentage-point changes.
- **Mean modules per student:** enrolments referencing both known students and known courses divided by all student records, including students with no enrolments. It counts enrolment rows, not distinct modules or credits. Other KPI definitions are explicit in `evaluate.py`; valid-looking values are not assumed correct.
- **Email measure:** counts institutional-format addresses on records; it does not test delivery or count distinct reachable people.

## 3. Pilot results

The regenerated result files are authoritative. These results replace the earlier version that automatically inferred graduation and evaluated fewer fields.

### 3.1 Accuracy against the reference

| table | cell_error_rate_dirty | cell_error_rate_cleaned | record_error_rate_dirty | record_error_rate_cleaned | lost_records_cleaned |
|---|---|---|---|---|---|
| students | 7.18% | 3.27% | 52.00% | 18.44% | 0 |
| enrolments | 2.41% | 3.16% | 9.34% | 7.20% | 92 |
| courses | 1.07% | 1.07% | 5.36% | 5.36% | 0 |

Cleaning retains three extra student records. It removes 92 reference enrolments from the working table: 90 are preserved in quarantine and two were dropped as duplicate enrolments. Loss from the working table is explicitly penalised in accuracy. Enrolment cell accuracy therefore worsens despite fewer rule flags.

### 3.2 Reliability of reported information

| KPI | truth | dirty | cleaned | error_dirty | error_cleaned |
|---|---|---|---|---|---|
| Active student headcount | 345.0 | 445.0 | 434.0 | 28.99% | 25.80% |
| Graduates on record | 594.0 | 541.0 | 508.0 | 8.92% | 14.48% |
| Total student records (people) | 1000.0 | 1050.0 | 1003.0 | 5.00% | 0.30% |
| Computer Science students | 131.0 | 122.0 | 131.0 | 6.87% | 0.00% |
| Student records with institutional-format email | 1000.0 | 921.0 | 942.0 | 7.90% | 5.80% |
| Courses currently offered | 53.0 | 56.0 | 56.0 | 5.66% | 5.66% |
| Mean grade (completed modules) | 61.65 | 64.41 | 61.7 | 4.48% | 0.08% |
| Pass rate (grade >= 40) | 0.9721 | 0.969 | 0.971 | 0.32% | 0.11% |
| Mean modules per student | 5.08 | 4.79 | 4.98 | 5.71% | 1.97% |

Student headcount and graduate totals remain wrong because status changes require source evidence. Removing duplicate graduate records can increase the relative graduate-count error while making person counts more accurate. This is a measured trade-off, not a failed experiment.

The duplicate matcher identifies 47 of 50 injected duplicate pairs, with 100% pair precision and 94% recall in this pilot. This does not establish safety on other populations: genuinely different people can share birth dates and similar names. A production implementation needs review thresholds and authoritative identifiers.

Record-level detection results are saved separately in `detection_metrics.csv`. Flagging an unchanged canonical student because a duplicate shares its email counts as a false positive under the strict cell-difference label; interpret this alongside pair-level metrics. Zero flags on the reference fixture establish performance only for that fixture.

### 3.3 Repeated mixed-error experiments

The following values are average **relative KPI errors** over 30 seeds. Intervals are percentile bootstrap 95% intervals for the mean, using 2,000 resamples and bootstrap seed 42. They describe variation within this synthetic design and are not population estimates for universities.

| stage | metric | runs | mean_relative_error | ci95_low | ci95_high |
|---|---|---|---|---|---|
| cleaned | Active student headcount | 30 | 25.08% | 24.56% | 25.58% |
| cleaned | Graduates on record | 30 | 14.86% | 14.81% | 14.91% |
| cleaned | Mean grade (completed modules) | 30 | 0.07% | 0.05% | 0.09% |
| cleaned | Total student records (people) | 30 | 0.13% | 0.09% | 0.16% |
| dirty | Active student headcount | 30 | 30.14% | 29.38% | 30.93% |
| dirty | Graduates on record | 30 | 10.07% | 9.82% | 10.32% |
| dirty | Mean grade (completed modules) | 30 | 3.72% | 3.42% | 4.01% |
| dirty | Total student records (people) | 30 | 5.00% | 5.00% | 5.00% |

Full per-run accuracy, KPI values, scenario counts and the other KPI summaries are committed in `results/experiment_*.csv`. The isolated scenarios allow attribution within this generator; combined pilot results alone cannot establish how much of a change is caused by a single error type.

## 4. Governance and supporting literature

Wang and Strong (1996) treat quality from the data consumer's perspective, including task context, representation and accessibility. This motivates evaluating useful reports alongside field errors. It does not make those additional dimensions measured outcomes of this experiment.

ISO/IEC 25012:2008 provides a model for structured-data quality and supports setting requirements and measures. The project's five operational rule groups are a practical selection, not an implementation of every ISO characteristic or a certification claim.

DAMA International presents DMBOK as a data-management framework covering governance and quality. The recommendations below are applications proposed by this project, not quoted prescriptions from an unread book chapter.

A university should assign owners for key datasets, validate values at entry, maintain shared identifiers and code lists, preserve audit trails, and give staff a queue for resolving uncertain records. Graduation should be confirmed by an authoritative academic decision. Course offering status should be confirmed by the responsible department. Quarantined enrolments need an owner and a correction process.

## 5. Limitations and next steps

- Data and error frequencies are synthetic, and the generator shares assumptions with the cleaner. Blind error injection by another person remains future work.
- Isolated error-family scenarios use one seed. Repeat these across multiple seeds before generalising their patterns.
- Matching thresholds and programme inference can make incorrect decisions on more complex populations. The tests cover a small set of regressions, not every possible mistake.
- Currentness checks identify suspicious records; authoritative verification has not been simulated, so pending cases remain inaccurate.
- SQLite tables are written without a database constraint experiment. Compare prevention with cleaning in future work.
- KPI values are rounded before relative errors are calculated, as specified by `kpis`; very small changes may be hidden by rounding.
- Before using real records, obtain the institution's permission and define appropriate privacy controls. No real student records are included here.

## 6. Reproduce and inspect

Use Python 3.11 or later in a virtual environment, install `requirements.txt`, then run:

```bash
python -m unittest discover -s tests -v
python src/evaluate.py
python src/experiments.py
```

The pilot overwrites generated data and pilot result tables. The repeated runner uses temporary databases and writes separate experiment CSV files. SQLite files are ignored by git and can be regenerated. `results/review_queue.csv` and `results/quarantine.csv` make pending actions inspectable.

## References and verification scope

Sources below were retrieved on 23 October 2026. ISO claims use its public abstract, and DAMA claims use its public overview; the full paid standard and DMBOK book were not inspected. The broader unverified bibliography and unsupported cost/compliance claims from the earlier draft have been removed.

1. Wang, R. Y., & Strong, D. M. (1996). Beyond accuracy: What data quality means to data consumers. *Journal of Management Information Systems, 12*(4), 5–33. https://doi.org/10.1080/07421222.1996.11518099. [Author-hosted text](https://web.mit.edu/tdqm/www/tdqmpub/beyondaccuracy_files/beyondaccuracy.html).
2. ISO/IEC. (2008). *ISO/IEC 25012:2008: Software engineering — Software product Quality Requirements and Evaluation (SQuaRE) — Data quality model*. [Official abstract](https://www.iso.org/standard/35736.html).
3. DAMA International. (n.d.). *DAMA Data Management Body of Knowledge (DAMA-DMBOK)*. [Official overview](https://dama.org/learning-resources/dama-data-management-body-of-knowledge-dmbok/).
