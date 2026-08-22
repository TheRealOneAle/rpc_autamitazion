import os
import sys
import unittest
import importlib.util


def load_module_from_path(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Load generarglobos/app.py
globos_app = load_module_from_path("globos_app", os.path.abspath("generarglobos/app.py"))
# Load generartabla/app.py
tabla_app = load_module_from_path("tabla_app", os.path.abspath("generartabla/app.py"))


class TestGraphicsPipeline(unittest.TestCase):

    def test_first_solution_card_generation(self):
        fs_data = {
            "problem_letter": "D",
            "team_name": "SaleEnOdeUno",
            "university": "Universidad Nacional de Colombia",
            "time_minutes": 22,
            "language": "C++",
            "color_hex": "#2ECC71",
        }
        os.makedirs("scratch", exist_ok=True)
        card_path = "scratch/test_fs_card.png"

        globos_app._generate_first_solution_card(
            letter=fs_data["problem_letter"],
            team_name=fs_data["team_name"],
            university=fs_data["university"],
            time_minutes=fs_data["time_minutes"],
            language=fs_data["language"],
            color_hex=fs_data["color_hex"],
            output_path=card_path,
        )

        self.assertTrue(os.path.exists(card_path))
        self.assertGreater(os.path.getsize(card_path), 5000)

    def test_elastic_css_generator(self):
        css_top5 = tabla_app._build_elastic_css(top_n=5, row_count=5)
        self.assertIn("1300px", css_top5)
        self.assertIn("26px", css_top5)

        css_top10 = tabla_app._build_elastic_css(top_n=10, row_count=10)
        self.assertIn("1650px", css_top10)
        self.assertIn("22px", css_top10)

        css_top15 = tabla_app._build_elastic_css(top_n=15, row_count=15)
        self.assertIn("1950px", css_top15)
        self.assertIn("19px", css_top15)

        css_top20 = tabla_app._build_elastic_css(top_n=20, row_count=20)
        self.assertIn("2250px", css_top20)
        self.assertIn("16px", css_top20)


if __name__ == "__main__":
    unittest.main()
