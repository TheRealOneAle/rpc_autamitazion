import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

import unittest
from unittest.mock import patch, MagicMock
from publisher.scheduler import _fetch_scoreboard_signature, _check_unfreeze_job
from publisher.orchestrator import _publish_for_user
import json


class TestUnfreezeAndImprovements(unittest.TestCase):

    def test_scoreboard_signature_generation(self):
        """Verifica que firmas de tableros idénticos generen el mismo hash y tableros distintos generen hashes diferentes."""
        board_5pm = {
            "success": True,
            "rows": [
                {"usernumber": 1, "problemas_resueltos": 5, "points": 450},
                {"usernumber": 2, "problemas_resueltos": 4, "points": 320},
            ]
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = board_5pm

        with patch("requests.get", return_value=mock_resp):
            sig1 = _fetch_scoreboard_signature("http://ms1", "2026", "06")

        self.assertIsNotNone(sig1)
        self.assertEqual(sig1["total_ac"], 9)
        self.assertEqual(sig1["count"], 2)

        # Mismo tablero debe generar idéntico hash
        with patch("requests.get", return_value=mock_resp):
            sig2 = _fetch_scoreboard_signature("http://ms1", "2026", "06")
        self.assertEqual(sig1["hash"], sig2["hash"])

        # Tablero descongelado con nuevo problema resuelto
        board_thawed = {
            "success": True,
            "rows": [
                {"usernumber": 1, "problemas_resueltos": 6, "points": 580},  # +1 AC en freeze
                {"usernumber": 2, "problemas_resueltos": 4, "points": 320},
            ]
        }
        mock_thawed_resp = MagicMock()
        mock_thawed_resp.status_code = 200
        mock_thawed_resp.json.return_value = board_thawed

        with patch("requests.get", return_value=mock_thawed_resp):
            sig_thawed = _fetch_scoreboard_signature("http://ms1", "2026", "06")

        self.assertNotEqual(sig1["hash"], sig_thawed["hash"])
        self.assertEqual(sig_thawed["total_ac"], 10)

    def test_unfreeze_detector_identifies_change_and_triggers_final(self):
        """Simula la comparación del monitor de descongelación cuando el tablero cambia."""
        user = MagicMock()
        user.username = "test_operator"
        user.is_active = True

        sig_5pm = {"hash": "hash_5pm", "total_ac": 5, "count": 2}
        sig_unfrozen = {"hash": "hash_unfrozen", "total_ac": 7, "count": 2}

        with patch("django.contrib.auth.models.User.objects.filter", return_value=[user]):
            with patch("publisher.scheduler._get_now_bogota") as mock_now:
                # Simular las 18:15 (después de congelamiento)
                mock_dt = MagicMock()
                mock_dt.hour = 18
                mock_dt.strftime.return_value = "18:15"
                mock_now.return_value = mock_dt

                with patch("publisher.models.UserConfig.objects.filter") as mock_uc:
                    mock_proceso = MagicMock()
                    mock_proceso.value = "true"
                    mock_uc.return_value.first.return_value = mock_proceso

                    with patch("publisher.orchestrator._get_config", return_value="http://ms1"):
                        with patch("publisher.orchestrator._user_contest_params", return_value=("2026", "06")):
                            with patch("publisher.scheduler._fetch_scoreboard_signature", return_value=sig_unfrozen):
                                with patch("publisher.models.SystemConfig.objects.filter") as mock_sc:
                                    mock_empty = MagicMock()
                                    mock_empty.first.return_value = None

                                    mock_base_qs = MagicMock()
                                    mock_base = MagicMock()
                                    mock_base.value = json.dumps(sig_5pm)
                                    mock_base_qs.first.return_value = mock_base

                                    mock_sc.side_effect = lambda key: mock_empty if "unfreeze_final_published" in key else (mock_base_qs if "frozen_5pm_sig" in key else mock_empty)

                                    with patch("publisher.models.SystemConfig.objects.update_or_create") as mock_sc_update:
                                        with patch("publisher.models.ExecutionLog.objects.create") as mock_exec_log:
                                            with patch("publisher.orchestrator.orchestrate_all") as mock_orch:
                                                _check_unfreeze_job()

                                                # Debe marcar la publicación como realizada
                                                mock_sc_update.assert_called_with(
                                                    key="unfreeze_final_published_2026/06",
                                                    defaults={'value': 'true'}
                                                )
                                                # Debe registrar en el log
                                                mock_exec_log.assert_called_once()
                                                # Debe ejecutar la publicación final!
                                                mock_orch.assert_called_once_with(final=True)

    def test_orchestrator_skips_hourly_publication_after_18_when_not_final(self):
        """Verifica que después de las 18:00 no se publiquen tablas regulares duplicadas congeladas."""
        user = MagicMock()
        user.username = "test_user"

        with patch("publisher.orchestrator._get_user_config", return_value="true"):
            with patch("datetime.datetime") as mock_dt:
                mock_now = MagicMock()
                mock_now.hour = 18
                mock_now.strftime.return_value = "18:00"
                mock_dt.now.return_value = mock_now

                with patch("publisher.orchestrator._user_contest_params") as mock_params:
                    # Al llamar sin final=True y sin force=True, debe omitir
                    _publish_for_user(user, final=False, force=False)
                    # No debe avanzar a consultar parámetros de contest ni publicar
                    mock_params.assert_not_called()

    def test_publish_first_solution_force_and_clear_from_db(self):
        """Verifica que publish_first_solution_event permita republicar con force=True y que clear_first_solutions funcione."""
        from publisher.orchestrator import publish_first_solution_event
        from publisher.models import FirstSolutionEvent

        user = MagicMock()
        user.username = "test_user"
        user.is_active = True

        fs_data = {
            "problem_letter": "A",
            "problem_name": "Antigravity",
            "team_name": "Los Ganadores",
            "university": "RPC University",
            "time_minutes": 25,
            "language": "C++",
        }

        # Simular registro existente
        existing_event = MagicMock()
        existing_event.success = True
        existing_event.post_id = "fb_12345"

        with patch("django.contrib.auth.models.User.objects.filter", return_value=[user]):
            with patch("publisher.models.SocialToken.objects.filter") as mock_token:
                mock_t = MagicMock()
                mock_t.access_token = "token"
                mock_t.page_id = "page"
                mock_token.return_value.order_by.return_value.first.return_value = mock_t

                with patch("publisher.orchestrator._user_contest_params", return_value=("2026", "08")):
                    with patch("publisher.models.FirstSolutionEvent.objects.filter") as mock_fs_filter:
                        mock_fs_filter.return_value.first.return_value = existing_event

                        # Sin force=True: debe retornar "Ya publicado" y NO llamar a facebook_publisher
                        with patch("publisher.facebook_publisher.publish_photo") as mock_pub:
                            ok, res = publish_first_solution_event(fs_data, user=user, force=False)
                            self.assertTrue(ok)
                            self.assertIn("Ya publicado", res)
                            mock_pub.assert_not_called()

                        # Con force=True: DEBE llamar a facebook_publisher y republicar
                        with patch("publisher.facebook_publisher.publish_photo", return_value="fb_new_99999") as mock_pub_force:
                            with patch("publisher.models.FirstSolutionEvent.objects.update_or_create") as mock_uoc:
                                with patch("publisher.models.ExecutionLog.objects.create") as mock_log:
                                    with patch("requests.post") as mock_post_card:
                                        mock_post_card.return_value.status_code = 200
                                        mock_post_card.return_value.content = b"image_bytes"
                                        ok, res = publish_first_solution_event(fs_data, user=user, force=True)
                                        self.assertTrue(ok)
                                        self.assertEqual(res, "fb_new_99999")
                                        mock_pub_force.assert_called_once()
                                        mock_uoc.assert_called_once()


if __name__ == "__main__":
    unittest.main()

