"""Regression tests for evidence preservation and measurement definitions."""
import random
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from checks import duplicate_pairs, load, run_checks
from clean import clean
from evaluate import accuracy, kpis, detection_metrics
from generate_data import make_truth, corrupt, save


class ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = dict(zip(('students', 'courses', 'enrolments'), make_truth(random.Random(42))))

    def test_clean_truth_has_no_flags_and_no_damage(self):
        with tempfile.TemporaryDirectory() as d:
            source, target = Path(d)/'truth.sqlite', Path(d)/'clean.sqlite'
            save(source, **self.tables)
            rules, _ = run_checks(source)
            self.assertEqual(rules.violations.sum(), 0)
            clean(source, target)
            measured = accuracy(self.tables, load(target))
            self.assertEqual(measured.cell_error_rate.sum(), 0)
            self.assertEqual(measured.lost_records.sum(), 0)

    def test_suspected_statuses_preserved_for_review(self):
        s, c, e, _ = corrupt(*self.tables.values(), random.Random(43), error_types={'outdated'})
        with tempfile.TemporaryDirectory() as d:
            source, target = Path(d)/'dirty.sqlite', Path(d)/'clean.sqlite'
            save(source, students=s, courses=c, enrolments=e)
            clean(source, target)
            out = load(target)
            self.assertEqual(list(out['students'].status), list(s.status))
            self.assertEqual(list(out['courses'].active), list(c.active))
            with sqlite3.connect(target) as con:
                self.assertGreater(con.execute('select count(*) from review_queue').fetchone()[0], 0)

    def test_zero_enrolment_students_and_invalid_links(self):
        db = {'students': pd.DataFrame({'student_id':[1,2], 'status':['active','active'],
                    'programme_code':['CS','CS'], 'email':['a@uni.example.ac.uk',None]}),
              'courses':pd.DataFrame({'course_code':['CS101'],'active':[1]}),
              'enrolments':pd.DataFrame({'student_id':[1,999,1], 'course_code':['CS101','CS101','unknown'],
                    'academic_year':[2025]*3,'grade':[50]*3})}
        self.assertEqual(kpis(db)['Mean modules per student'], .5)

    def test_all_non_key_fields_measured(self):
        changed = {k:v.copy() for k,v in self.tables.items()}
        changed['students'].loc[0,'last_updated']='1900-01-01'
        changed['courses'].loc[0,'credits']=999
        self.assertTrue((accuracy(self.tables,changed).set_index('table').loc[['students','courses'],'cell_error_rate']>0).all())

    def test_duplicate_cluster_and_distinct_person(self):
        s=pd.DataFrame({'student_id':[1,2,3,4], 'first_name':['Amira']*3+['Oliver'],
             'last_name':['Smith']*3+['Nguyen'], 'dob':['2000-01-01']*4,
             'enrol_year':[2019]*4, 'email':['a@x','a@x','b@x','c@x']})
        self.assertEqual(duplicate_pairs(s),[(1,2),(1,3)])

    def test_detection_compares_numeric_text_semantically(self):
        truth = {k:v.copy() for k,v in self.tables.items()}
        dirty = {k:v.copy() for k,v in truth.items()}
        dirty['enrolments']['grade'] = dirty['enrolments'].grade.map(lambda v: str(v) if pd.notna(v) else None)
        result = detection_metrics(truth,dirty,{k:set() for k in truth})
        self.assertTrue(all(r['false_negative']==0 for r in result))

    def test_injection_isolation_and_zero_scale(self):
        for family in ['missing','outdated','invalid','inconsistent_code','inconsistent_format']:
            *_, log=corrupt(*self.tables.values(), random.Random(42), error_types={family})
            self.assertEqual(set(log.error_type),{family})
        *_, log=corrupt(*self.tables.values(),random.Random(42),scale=0)
        self.assertTrue(log.empty)

    def test_impossible_date_and_text_grade_flagged(self):
        db={k:v.copy() for k,v in self.tables.items()}
        db['students'].loc[0,'dob']='2000-99-99'
        db['enrolments']['grade']=db['enrolments'].grade.astype(object)
        db['enrolments'].loc[0,'grade']='oops'
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'bad.sqlite'
            save(path,**db)
            rules,_=run_checks(path)
        violations=rules.set_index('rule').violations
        self.assertEqual(violations['dob not ISO-8601 (YYYY-MM-DD)'],1)
        self.assertEqual(violations['grade outside 0-100'],1)

if __name__=='__main__':
    unittest.main()
