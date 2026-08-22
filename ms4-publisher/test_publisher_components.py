import unittest
from publisher.description_builder import build_description, build_first_solution_description


class TestDescriptionBuilder(unittest.TestCase):

    def setUp(self):
        self.stats = {
            "total_teams": 120,
            "total_submissions": 450,
            "accepted_submissions": 180,
            "teams_with_solved": 85,
        }
        self.mock_user = {
            "competition_name": "Competencia 06 RPC 2026",
            "activated_by": "Juan Pérez",
        }

    def test_latam_description(self):
        desc = build_description(
            user=self.mock_user,
            competition_data=self.stats,
            scope="LATAM",
            top_n=10,
        )
        self.assertIn("Top 10 Latinoamérica", desc)
        self.assertIn("Competencia 06 RPC 2026", desc)
        self.assertIn("450 envíos totales", desc)
        self.assertIn("85 de 120 equipos", desc)
        self.assertIn("gracias Juan Pérez", desc)
        self.assertIn("#TodosSomosRPC", desc)

    def test_country_description(self):
        desc = build_description(
            user=self.mock_user,
            competition_data=self.stats,
            scope="CO",
            top_n=5,
        )
        self.assertIn("Top 5 Colombia 🇨🇴", desc)
        self.assertIn("#Colombia", desc)
        self.assertIn("450 envíos totales", desc)

    def test_first_solution_description(self):
        fs_data = {
            "problem_letter": "A",
            "problem_name": "Array Sorting",
            "team_name": "Los Algorítmicos",
            "university": "Universidad Francisco de Paula Santander",
            "country_code": "CO",
            "country_name": "Colombia",
            "time_minutes": 14,
            "language": "C++",
        }
        desc = build_first_solution_description(
            user=self.mock_user,
            fs_data=fs_data,
        )
        self.assertIn("¡FIRST SOLUTION - PROBLEMA A!", desc)
        self.assertIn("Los Algorítmicos", desc)
        self.assertIn("Universidad Francisco de Paula Santander", desc)
        self.assertIn("minuto 14", desc)
        self.assertIn("C++", desc)
        self.assertIn("#FirstSolution", desc)


if __name__ == "__main__":
    unittest.main()
