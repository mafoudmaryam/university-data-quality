# The project in simple language

Author: Maryam Mafoud

## 1. What are we investigating?

A university uses records to count students, prepare reports and calculate grades. We ask how mistakes in those records change the answers.

We measure report accuracy. We are not testing server availability or every part of a real university system.

## 2. Create an answer we know is correct

`generate_data.py` creates fictional students, courses and enrolments. An enrolment links a student to a course in an academic year. The original version is called **ground truth**: our reference answer.

The pilot has 1,000 students, 56 courses and 5,084 enrolments. SQLite stores the tables in a database file.

## 3. Add mistakes deliberately

We copy the reference data and add duplicates, empty fields, outdated statuses, inconsistent labels, impossible grades and broken links. The injection log records these changes, including changed update dates.

Different errors may affect the same record. An injection count is therefore different from the number of wrong records.

## 4. Check the records

`checks.py` runs 19 rules. It checks whether required values exist, records look duplicated, formats and values are allowed, links agree, and information might be outdated.

A **flag** means a rule found something suspicious. It does not prove the record is wrong. A value can also look valid while being incorrect.

## 5. Clean carefully

`clean.py` standardises known labels and formats, merges probable duplicates, fills some missing programmes using course histories, blanks impossible grades and moves broken enrolments to quarantine.

**Quarantine** means keeping uncertain records aside for correction. It does not restore the correct information, and removing a real enrolment from reports is counted as a loss.

An overdue student is added to a **review queue**, not automatically marked graduated. A department must confirm whether a course is retired. The software does not invent these decisions.

## 6. Measure three different things

- **Rule flags:** how many records fail checks?
- **Actual accuracy:** how many values differ from the reference? Every non-key field is included, such as update dates and course credits.
- **Reporting accuracy:** how far are student totals, grade averages and other reports from the correct answers?

We also measure **precision** (how many flagged cases are real errors) and **recall** (how many actual errors were found). Duplicate matching has a separate pair-level comparison.

Mean modules per student includes students with no enrolments and excludes links to unknown students or courses. Institutional-format email counts do not prove that messages can be delivered.

## 7. What changed in the findings?

See the generated [pilot results](../results/results.md) and [full report](../report.md) for current numbers. Cleaning improves many values, but outdated statuses remain pending verification. Some reports therefore remain wrong, and removing duplicate records can make an already incomplete graduate total worse.

This is useful evidence: fewer rule violations do not guarantee accurate reports, and software cannot recover facts it does not know.

## 8. Repeat the experiment

`experiments.py` uses 30 different random seeds for combined errors. A seed makes a random experiment repeatable. It also tests eight error families separately at three probability multipliers, plus a zero-error control: 55 scenarios in total.

The isolated tests share the same fictional university. They help identify an error family's effect within this simulation, but one seed per isolated setting is not enough for broad conclusions.

A **confidence interval** in the summary describes uncertainty about the mean across the synthetic runs. It does not establish what happens in every real university.

## 9. Why governance matters

Data governance means deciding who owns records, which rules apply and who resolves uncertain cases. The experiment supports a practical workflow: validate entries, preserve history, monitor quality, assign corrections and verify status changes using authoritative evidence.

The report links the sources actually checked. It does not claim to implement a complete international standard.

## 10. Run it

Follow [README.md](../README.md) for setup. Run tests, the pilot and repeated experiments. The pilot writes CSV result tables, a quarantine export and a review queue. Generated SQLite databases can be recreated and are not committed.
