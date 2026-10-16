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
            self.assertEqual(fs.get('enabled'), 'Yes')
            self.assertTrue(fs.get('is_enabled'))
            print(f"  FS Problem {fs['problem_letter']}: {fs['team_name']} ({fs['university']}) min {fs['time_minutes']} [enabled={fs.get('enabled')}]")

    def test_first_solutions_filters_disabled_teams(self):
        """Verifica que equipos con enabled != 'Yes' sean ignorados y el first solve sea del primer equipo con enabled == 'Yes'."""
        from unittest.mock import patch

        mock_runs = [
            # Problema C: equipo_deshabilitado resuelve en min 15 con 'No'
            {
                "run_number": 101,
                "site": 1,
                "username": "disabled_team",
                "time_minutes": 15,
                "letter": "C",
                "language": "C++",
                "verdict": "YES",
                "is_solved": True,
            },
            # Problema C: equipo_habilitado resuelve en min 25 con 'Yes'
            {
                "run_number": 102,
                "site": 1,
                "username": "enabled_team",
                "time_minutes": 25,
                "letter": "C",
                "language": "Python3",
                "verdict": "YES",
                "is_solved": True,
            },
            # Problema X: solo resuelto por equipo_deshabilitado
            {
                "run_number": 103,
                "site": 1,
                "username": "disabled_team",
                "time_minutes": 5,
                "letter": "X",
                "language": "Java",
                "verdict": "YES",
                "is_solved": True,
            },
        ]

        mock_users_map = {
            "disabled_team": {
                "username": "disabled_team",
                "userfullname": "Disabled Team Name",
                "university": "Univ A",
                "country": "CO",
                "enabled": "No",
                "is_enabled": False,
            },
            "enabled_team": {
                "username": "enabled_team",
                "userfullname": "Enabled Team Name",
                "university": "Univ B",
                "country": "PE",
                "enabled": "Yes",
                "is_enabled": True,
            },
        }

        with patch("app._get_runs_data", return_value=mock_runs):
            with patch("app._get_users_map", return_value=mock_users_map):
                resp = self.client.get('/api/first-solutions')
                self.assertEqual(resp.status_code, 200)
                data = resp.get_json()
                self.assertTrue(data['success'])

                fs_map = {fs['problem_letter']: fs for fs in data['first_solutions']}
                # Problema C debe pertenecer a enabled_team (min 25), NO a disabled_team (min 15)
                self.assertIn('C', fs_map)
                self.assertEqual(fs_map['C']['username'], 'enabled_team')
                self.assertEqual(fs_map['C']['time_minutes'], 25)
                self.assertEqual(fs_map['C']['enabled'], 'Yes')

                # Problema X no debe tener First Solution porque solo lo resolvió un equipo con enabled "No"
                self.assertNotIn('X', fs_map)

    def test_stats_endpoint(self):
        resp = self.client.get('/api/stats')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertGreater(data['total_submissions'], 0)
        print(f"Stats: {data['total_submissions']} envios, {data['accepted_submissions']} AC, tasa: {data['acceptance_rate']}%")


if __name__ == '__main__':
    unittest.main()
