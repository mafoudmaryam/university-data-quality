# The project explained from the beginning

## 1. The big idea

Organisations make decisions with data. A university uses its student records to count how many students it has, plan classes, send emails, report to regulators and get funding. If those records are wrong, every report built on them is wrong too.

Your research question asks **how much** bad data damages the information a system produces. To answer "how much", you need to measure, and to measure an error you need to know the correct answer. That's why the project uses data we invented ourselves.

## 2. Step 1: build a "perfect" university (the ground truth)

File: `src/generate_data.py`

The script invents a small university with three tables, like sheets in a spreadsheet:

| Table | What it holds | Example row |
|---|---|---|
| **students** (1,000) | One row per student: name, email, date of birth, programme, start year, status | Emily Silva, emily.silva@uni.example.ac.uk, 1998-06-14, CS, 2023, active |
| **courses** (56) | The modules each programme offers | CS101, "Computer Science module 1", 15 credits |
| **enrolments** (5,084) | Which student took which course in which year, and their grade | student 17, CS101, 2023, grade 64 |

This version is 100% correct. It's saved as `truth.sqlite` (SQLite is a small database stored in a single file). It plays the role of "what is really true", which you never have in a real university.

## 3. Step 2: break it on purpose (error injection)

The same script copies the perfect data and deliberately damages it, the way real data gets damaged. It does this in four ways, which match the four problems named in your research topic:

| Problem | What it looks like | Real-life cause |
|---|---|---|
| **Duplicate** | The same student entered twice under two IDs, e.g. "Emily Silva" and "Emily Sliva" | A student applies twice, or two offices each create a record |
| **Incomplete** | Empty email, date of birth, programme or grade | A field that wasn't required on a form |
| **Outdated** | A student who graduated in 2025 is still marked "active" | Nobody updated the record |
| **Inconsistent** | "CS", "cs", "Comp Sci" all meaning Computer Science; dates written as 14/06/1998 or 06-14-1998 | Different people and systems using different conventions |

It also adds a few **invalid** values (a grade of 999, an email with no "@") and **broken links** (an enrolment for a student who doesn't exist).

In total it injected **1,248 errors**, and it wrote every one of them down in `injection_log.csv`. That log is what lets you check later whether each error was caught.

The damaged copy is `dirty.sqlite`. It represents a typical real university database.

## 4. Step 3: data profiling (looking for problems)

File: `src/checks.py`

Profiling means inspecting the data to see what's wrong with it. The script runs **19 rules**, each a yes/no test on every row. They are grouped by the standard **data-quality dimensions** used in the literature (DAMA-DMBOK, ISO/IEC 25012):

| Dimension | Plain meaning | Example rule |
|---|---|---|
| Completeness | Is anything missing? | "Every student has an email" |
| Uniqueness | Is anything recorded twice? | "No two students share a date of birth and a near-identical name" |
| Validity | Does each value follow the format and allowed list? | "Grade is between 0 and 100", "Programme is one of CS, IS, BUS..." |
| Consistency | Do the tables agree with each other? | "Every enrolment points to a student who exists" |
| Timeliness | Is the data up to date? | "No one is still 'active' after their 3-year degree ended" |

Duplicates are found with **fuzzy matching**. Records are grouped by date of birth and start year, and names are compared by similarity score, so "Silva" and "Sliva" (about 90% similar) count as a match. Records that share the same email are also treated as one person.

As a sanity check, the rules find **0 problems in the perfect data**. They never complain about correct data.

## 5. Step 4: cleaning

File: `src/clean.py`

Cleaning fixes what can be fixed, in this order:

1. **Standardise.** Tidy names ("  ETHAN " becomes "Ethan"), lower-case emails, put back a missing "@", convert all dates to one format (YYYY-MM-DD), and map every variant to one official code ("Comp Sci" becomes "CS", "U.K." becomes "United Kingdom").
2. **Merge duplicates.** Keep the older record, fill its gaps from the duplicate (survivorship), move the duplicate's enrolments onto the kept record, then delete the duplicate.
3. **Fill gaps where the answer can be worked out.** A student's programme can be inferred from the courses they take. A missing grade can't be guessed, so it stays empty.
4. **Handle invalid and broken rows.** Impossible grades are blanked. Enrolments for students who don't exist are moved to a **quarantine** table, so they don't pollute reports but aren't lost either.
5. **Update outdated records.** Students past their end date with no current courses are set to "graduated". Courses with no enrolments for 2 years are marked retired.

The result is `cleaned.sqlite`.

## 6. Step 5: measuring (the experiment)

File: `src/evaluate.py`. This one script runs everything above and then measures at three levels:

**A. Rule violations before and after.** This is what a real organisation can see.
Students failing at least one rule went from **51.7% to 9.8%**.

**B. Accuracy against the truth.** This is only possible because we built the truth.
Each cell is compared with the perfect data. Wrong cells in the students table went from **7.8% to 1.1%**.
Fix rate by error type:
- Codes, formats and outdated records: 100% fixed
- Duplicates: 94% fixed (47 of 50)
- Missing values: only 10% fixed

**C. Reliability of the information.** This is the heart of the research question.
These are numbers a university would actually report:

| Report | True | From dirty data | After cleaning |
|---|---|---|---|
| Active students | 345 | 445 (**29% too high**) | 345 |
| Average grade | 61.65 | 64.41 | 61.70 |
| Courses offered | 53 | 56 | 53 |

## 7. What it means

- **Small errors cause big mistakes.** About 9% of records were outdated, but the active-student count was 29% wrong, because all those errors landed in the same number.
- **A few extreme values move averages.** Only 42 impossible grades (1%) shifted the average by almost 3 points.
- **Errors spread.** Duplicate students split their course history in two, so transcripts and progression checks would be wrong.
- **Cleaning can't recreate lost information.** Missing data mostly stays missing. Prevention (required fields, validation when data is entered, data owners) works better than cleaning afterwards. This is what the governance frameworks in the report recommend.

## 8. The governance part

The report's Section 4 reviews the main frameworks:
- **DAMA-DMBOK**: the textbook for data management. It defines the quality dimensions used above and roles like data owner and data steward.
- **ISO 8000**: the international standard for data quality and how to manage it as a process.
- **ISO/IEC 25012**: a standard list of data-quality characteristics.
- **GDPR**: the law requiring personal data to be accurate and kept up to date.

Your experiment provides evidence for why universities should follow them.

## 9. Where everything is

```
report.md          the full research write-up (plan, results, governance, references)
src/               the 4 Python scripts described above
data/              the dirty data as CSV files + the log of injected errors
results/           all result tables (results.md is the readable version)
```

To run it yourself: install Python and pandas, then run `cd src && python3 evaluate.py`.

## 10. What comes next

The first planned step is to **repeat the experiment many times** (30 random versions of the university) at different error levels (1% to 20%). That turns one result into a reliable average, and produces a chart showing how reporting errors grow as data quality gets worse.
