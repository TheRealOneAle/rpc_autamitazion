import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from unittest.mock import patch
from publisher.description_builder import build_description


SAMPLE_DATA = {
    "teams": [
        {"userfullname": "Team Alpha", "problemas_resueltos": 7, "points": 420},
        {"userfullname": "Team Beta", "problemas_resueltos": 5, "points": 310},
        {"userfullname": "Team Gamma", "problemas_resueltos": 4, "points": 280},
        {"userfullname": "Team Delta", "problemas_resueltos": 3, "points": 200},
    ]
}


def _mock_config(key, default=""):
    cfg = {
        "competition_name": "Competencia 02 RPC 2026",
        "landing_page_url": "https://rpc.ufps.edu.co",
    }
    return cfg.get(key, default)


def test_contains_hashtags():
    with patch("publisher.description_builder._get_config", side_effect=_mock_config):
        text = build_description(SAMPLE_DATA)
    assert "#TodosSomosRPC" in text
    assert "#CreciendoTodosJuntos" in text


def test_contains_landing_url():
    with patch("publisher.description_builder._get_config", side_effect=_mock_config):
        text = build_description(SAMPLE_DATA)
    assert "rpc.ufps.edu.co" in text


def test_contains_top3():
    with patch("publisher.description_builder._get_config", side_effect=_mock_config):
        text = build_description(SAMPLE_DATA)
    assert "Team Alpha" in text
    assert "Team Beta" in text
    assert "Team Gamma" in text
    assert "Team Delta" not in text


def test_contains_competition_name():
    with patch("publisher.description_builder._get_config", side_effect=_mock_config):
        text = build_description(SAMPLE_DATA)
    assert "Competencia 02 RPC 2026" in text


def test_contains_team_count():
    with patch("publisher.description_builder._get_config", side_effect=_mock_config):
        text = build_description(SAMPLE_DATA)
    assert "4" in text


if __name__ == "__main__":
    import sys
    tests = [test_contains_hashtags, test_contains_landing_url, test_contains_top3,
             test_contains_competition_name, test_contains_team_count]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{len(tests)-failed}/{len(tests)} tests pasaron")
    sys.exit(failed)
