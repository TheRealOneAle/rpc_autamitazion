import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from unittest.mock import patch, MagicMock
from publisher.orchestrator import orchestrate_publication


SAMPLE_COMPETITION = {
    "teams": [
        {"userfullname": "Alpha", "problemas_resueltos": 7},
        {"userfullname": "Beta", "problemas_resueltos": 5},
    ]
}


def test_skipped_when_proceso_inactive():
    with patch("publisher.orchestrator._get_config", return_value="false"):
        with patch("publisher.models.PublicationLog.objects.create") as mock_create:
            orchestrate_publication()
            mock_create.assert_called_once_with(status="SKIPPED")


def test_success_log_created():
    def mock_config(key, default=""):
        cfg = {"proceso_activo": "true", "ms1_url": "http://ms1:8001", "ms2_url": "http://ms2:8002"}
        return cfg.get(key, default)

    mock_r1 = MagicMock()
    mock_r1.json.return_value = SAMPLE_COMPETITION
    mock_r2 = MagicMock()
    mock_r2.content = b"fake_png"

    with patch("publisher.orchestrator._get_config", side_effect=mock_config):
        with patch("publisher.orchestrator._fetch_with_retry", side_effect=[mock_r1, mock_r2]):
            with patch("publisher.orchestrator.build_description", return_value="texto"):
                with patch("publisher.orchestrator.publish_photo", return_value="POST_123"):
                    with patch("publisher.orchestrator.publish_ranking_event"):
                        with patch("publisher.models.PublicationLog.objects.create") as mock_create:
                            orchestrate_publication()

    mock_create.assert_called_once()
    call_kwargs = mock_create.call_args[1]
    assert call_kwargs["status"] == "SUCCESS"
    assert call_kwargs["post_id"] == "POST_123"


def test_error_log_created_on_ms1_failure():
    def mock_config(key, default=""):
        return "true" if key == "proceso_activo" else default

    with patch("publisher.orchestrator._get_config", side_effect=mock_config):
        with patch("publisher.orchestrator._fetch_with_retry", side_effect=Exception("MS1 down")):
            with patch("publisher.models.PublicationLog.objects.create") as mock_create:
                orchestrate_publication()

    call_kwargs = mock_create.call_args[1]
    assert call_kwargs["status"] == "ERROR"
    assert "MS1 down" in call_kwargs["error_message"]


def test_error_log_on_facebook_failure():
    def mock_config(key, default=""):
        cfg = {"proceso_activo": "true", "ms1_url": "http://ms1:8001", "ms2_url": "http://ms2:8002"}
        return cfg.get(key, default)

    mock_r1 = MagicMock()
    mock_r1.json.return_value = SAMPLE_COMPETITION
    mock_r2 = MagicMock()
    mock_r2.content = b"fake_png"

    with patch("publisher.orchestrator._get_config", side_effect=mock_config):
        with patch("publisher.orchestrator._fetch_with_retry", side_effect=[mock_r1, mock_r2]):
            with patch("publisher.orchestrator.build_description", return_value="texto"):
                with patch("publisher.orchestrator.publish_photo", side_effect=Exception("FB error")):
                    with patch("publisher.models.PublicationLog.objects.create") as mock_create:
                        orchestrate_publication()

    call_kwargs = mock_create.call_args[1]
    assert call_kwargs["status"] == "ERROR"


if __name__ == "__main__":
    import sys
    tests = [test_skipped_when_proceso_inactive, test_success_log_created,
             test_error_log_created_on_ms1_failure, test_error_log_on_facebook_failure]
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
