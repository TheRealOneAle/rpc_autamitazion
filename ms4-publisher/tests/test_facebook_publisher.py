import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from unittest.mock import patch, MagicMock
from publisher.facebook_publisher import publish_photo, FacebookTokenExpiredError, FacebookRateLimitError


TOKEN_OBJ = MagicMock(access_token="test_token_123", page_id="111222333")


def _mock_get_token():
    return TOKEN_OBJ.access_token, TOKEN_OBJ.page_id


def test_publish_success():
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"post_id": "999888777_111"}

    with patch("publisher.facebook_publisher._get_token_and_page", return_value=("tok", "pid")):
        with patch("requests.post", return_value=mock_resp):
            post_id = publish_photo(b"fake_image", "Texto de prueba")

    assert post_id == "999888777_111"


def test_publish_calls_correct_endpoint():
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"post_id": "abc123"}

    with patch("publisher.facebook_publisher._get_token_and_page", return_value=("mytoken", "mypage")):
        with patch("requests.post", return_value=mock_resp) as mock_post:
            publish_photo(b"img", "desc")
            url_called = mock_post.call_args[0][0]

    assert "mypage" in url_called
    assert "photos" in url_called
    data_sent = mock_post.call_args[1]["data"]
    assert data_sent["access_token"] == "mytoken"
    assert data_sent["message"] == "desc"


def test_token_expired_raises():
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.json.return_value = {"error": {"code": 190, "message": "Invalid OAuth access token"}}

    with patch("publisher.facebook_publisher._get_token_and_page", return_value=("expired", "page")):
        with patch("requests.post", return_value=mock_resp):
            try:
                publish_photo(b"img", "desc")
                assert False, "Debería haber lanzado excepción"
            except FacebookTokenExpiredError:
                pass


def test_rate_limit_raises():
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.json.return_value = {"error": {"code": 4, "message": "Rate limit reached"}}

    with patch("publisher.facebook_publisher._get_token_and_page", return_value=("tok", "page")):
        with patch("requests.post", return_value=mock_resp):
            try:
                publish_photo(b"img", "desc")
                assert False, "Debería haber lanzado FacebookRateLimitError"
            except FacebookRateLimitError:
                pass


if __name__ == "__main__":
    import sys
    tests = [test_publish_success, test_publish_calls_correct_endpoint,
             test_token_expired_raises, test_rate_limit_raises]
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
