import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app


class BocaScraperTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_ranking_default(self):
        resp = self.client.get('/api/ranking')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertLessEqual(len(data['rows']), 10)
        print(f"Ranking default rows: {len(data['rows'])}")

    def test_ranking_country_filter(self):
        resp = self.client.get('/api/ranking?country=CO&top_n=5')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertLessEqual(len(data['rows']), 5)
        for r in data['rows']:
            self.assertEqual(r['country'], 'CO')
        print(f"Ranking Colombia top 5 rows: {len(data['rows'])}")

    def test_countries_endpoint(self):
        resp = self.client.get('/api/countries')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertGreater(data['total_countries'], 0)
        print(f"Countries detected: {[c['code'] for c in data['countries']]}")

    def test_universities_endpoint(self):
        resp = self.client.get('/api/universities')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertGreater(data['total_universities'], 0)
        print(f"Total universities detected: {data['total_universities']}")

    def test_first_solutions_endpoint(self):
        resp = self.client.get('/api/first-solutions')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertGreater(data['solved_problems_count'], 0)
        print(f"First solutions count: {data['solved_problems_count']}")
        for fs in data['first_solutions']:
            print(f"  FS Problem {fs['problem_letter']}: {fs['team_name']} ({fs['university']}) min {fs['time_minutes']}")

    def test_stats_endpoint(self):
        resp = self.client.get('/api/stats')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertGreater(data['total_submissions'], 0)
        print(f"Stats: {data['total_submissions']} envios, {data['accepted_submissions']} AC, tasa: {data['acceptance_rate']}%")


if __name__ == '__main__':
    unittest.main()
