# pylint: disable=protected-access
"""Unit tests for github_action.cloud_client.CloudClient."""

import json
import urllib.error
import urllib.request
from io import BytesIO
from unittest.mock import MagicMock, patch, call

import pytest

from github_action.cloud_client import (
    CloudClient,
    CloudClientError,
    CloudConnectionError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(
    cloud_url="https://cloud.example.com",
    cloud_token="secret-token",
    max_retries=3,
):
    return CloudClient(cloud_url, cloud_token, max_retries=max_retries)

def _mock_response(body: dict | str, status: int = 200):
    """Return a mock context-manager that urlopen can return."""
    if isinstance(body, dict):
        raw = json.dumps(body).encode()
    else:
        raw = body.encode()

    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cm)
    cm.__exit__ = MagicMock(return_value=False)
    cm.read.return_value = raw
    return cm

def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://cloud.example.com/api/v1/grading-configs/cfg-1",
        code=code,
        msg=f"HTTP {code}",
        hdrs=None,
        fp=None,
    )

# ---------------------------------------------------------------------------
# CloudClient.__init__
# ---------------------------------------------------------------------------

class TestCloudClientInit:
    def test_trailing_slash_stripped_from_base_url(self):
        """Asserts base URL trailing slashes are normalised."""
        client = CloudClient("https://cloud.example.com///", "tok")
        assert client._base_url == "https://cloud.example.com"

    def test_default_timeout_and_retry_values(self):
        """Asserts default timeouts and max_retries match module constants."""
        client = CloudClient("https://cloud.example.com", "tok")
        assert client.connect_timeout == 10.0
        assert client.read_timeout == 30.0
        assert client.max_retries == 3

    def test_custom_timeouts_stored(self):
        """Asserts custom timeouts are stored on the instance."""
        client = CloudClient(
            "https://cloud.example.com",
            "tok",
            connect_timeout=5.0,
            read_timeout=60.0,
        )
        assert client.connect_timeout == 5.0
        assert client.read_timeout == 60.0

# ---------------------------------------------------------------------------
# get_grading_config
# ---------------------------------------------------------------------------

class TestGetGradingConfig:
    def test_calls_correct_url(self):
        """Asserts the correct endpoint URL is called for a given config ID."""
        client = _make_client()
        mock_resp = _mock_response({"template_name": "python"})

        captured_req = []

        def fake_urlopen(req, timeout=None):
            captured_req.append(req)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen), patch(
            "time.sleep"
        ):
            client.get_grading_config("cfg-42")

        assert len(captured_req) == 1
        assert captured_req[0].full_url == "https://cloud.example.com/api/v1/configs/id/cfg-42"

    def test_returns_parsed_json(self):
        """Asserts the response body is parsed as JSON and returned."""
        client = _make_client()
        config = {"template_name": "python", "criteria": {"base": {}}}
        mock_resp = _mock_response(config)

        with patch("urllib.request.urlopen", return_value=mock_resp), patch(
            "time.sleep"
        ):
            result = client.get_grading_config("cfg-1")

        assert result == config

    def test_authorization_header_sent(self):
        """Asserts the Bearer token is included in the Authorization header."""
        client = CloudClient("https://cloud.example.com", "my-secret")
        mock_resp = _mock_response({})
        captured = []

        def fake_urlopen(req, timeout=None):
            captured.append(req)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen), patch(
            "time.sleep"
        ):
            client.get_grading_config("cfg-1")

        assert captured[0].get_header("Authorization") == "Bearer my-secret"

    def test_token_not_in_error_message_on_404(self):
        """Asserts the bearer token is not leaked in 4xx error messages."""
        client = CloudClient("https://cloud.example.com", "super-secret-token")

        with patch("urllib.request.urlopen", side_effect=_http_error(404)), patch(
            "time.sleep"
        ):
            with pytest.raises(CloudClientError) as exc_info:
                client.get_grading_config("cfg-missing")

        assert "super-secret-token" not in str(exc_info.value)

# ---------------------------------------------------------------------------
# submit_external_result
# ---------------------------------------------------------------------------

class TestSubmitExternalResult:
    def test_calls_correct_url_with_post(self):
        """Asserts POST is used and the correct URL is targeted."""
        client = _make_client()
        mock_resp = _mock_response({})
        captured = []

        def fake_urlopen(req, timeout=None):
            captured.append(req)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen), patch(
            "time.sleep"
        ):
            client.submit_external_result({"score": 90.0})

        req = captured[0]
        assert req.full_url == "https://cloud.example.com/api/v1/submissions/external-results"
        assert req.method == "POST"

    def test_payload_serialised_as_json(self):
        """Asserts the payload dict is sent as JSON in the request body."""
        client = _make_client()
        mock_resp = _mock_response({})
        captured = []

        def fake_urlopen(req, timeout=None):
            captured.append(req)
            return mock_resp

        payload = {"score": 75.5, "status": "success"}

        with patch("urllib.request.urlopen", side_effect=fake_urlopen), patch(
            "time.sleep"
        ):
            client.submit_external_result(payload)

        sent_body = json.loads(captured[0].data)
        assert sent_body == payload

    def test_returns_empty_dict_for_empty_response(self):
        """Asserts an empty response body returns an empty dict."""
        client = _make_client()
        mock_resp = _mock_response("")

        with patch("urllib.request.urlopen", return_value=mock_resp), patch(
            "time.sleep"
        ):
            result = client.submit_external_result({"score": 0.0})

        assert result == {}

# ---------------------------------------------------------------------------
# Error handling — 4xx (CloudClientError, no retry)
# ---------------------------------------------------------------------------

class TestFourXxErrors:
    @pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
    def test_4xx_raises_cloud_client_error_immediately(self, code):
        """Asserts CloudClientError is raised without retrying for 4xx responses."""
        client = _make_client(max_retries=3)

        with patch(
            "urllib.request.urlopen", side_effect=_http_error(code)
        ) as mock_open, patch("time.sleep") as mock_sleep:
            with pytest.raises(CloudClientError) as exc_info:
                client.get_grading_config("cfg-1")

        # urlopen called exactly once — no retries
        mock_open.assert_called_once()
        mock_sleep.assert_not_called()
        assert exc_info.value.status_code == code

    def test_4xx_error_message_is_actionable(self):
        """Asserts the 4xx error message instructs the user to check their configuration."""
        client = _make_client()

        with patch("urllib.request.urlopen", side_effect=_http_error(404)), patch(
            "time.sleep"
        ):
            with pytest.raises(CloudClientError) as exc_info:
                client.get_grading_config("cfg-bad")

        msg = str(exc_info.value)
        assert "404" in msg
        assert "configuration ID" in msg or "config" in msg.lower()

# ---------------------------------------------------------------------------
# Error handling — 5xx (retry, then CloudConnectionError)
# ---------------------------------------------------------------------------

class TestFiveXxRetry:
    def test_5xx_retried_up_to_max_retries(self):
        """Asserts urlopen is called max_retries+1 times on persistent 5xx."""
        client = _make_client(max_retries=2)

        with patch(
            "urllib.request.urlopen", side_effect=_http_error(503)
        ) as mock_open, patch("time.sleep"):
            with pytest.raises(CloudConnectionError):
                client.get_grading_config("cfg-1")

        assert mock_open.call_count == 3  # 1 initial + 2 retries

    def test_5xx_succeeds_on_second_attempt(self):
        """Asserts a successful response after one 5xx failure returns the payload."""
        client = _make_client(max_retries=2)
        config = {"template_name": "api"}
        mock_resp = _mock_response(config)

        call_count = [0]

        def flaky_urlopen(req, timeout=None):
            call_count[0] += 1
            if call_count[0] == 1:
                raise _http_error(500)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=flaky_urlopen), patch(
            "time.sleep"
        ):
            result = client.get_grading_config("cfg-1")

        assert result == config
        assert call_count[0] == 2

    def test_5xx_raises_connection_error_after_exhausting_retries(self):
        """Asserts CloudConnectionError is raised after all retries are exhausted."""
        client = _make_client(max_retries=1)

        with patch("urllib.request.urlopen", side_effect=_http_error(500)), patch(
            "time.sleep"
        ):
            with pytest.raises(CloudConnectionError):
                client.get_grading_config("cfg-1")

    def test_exponential_backoff_delays_used(self):
        """Asserts time.sleep is called with exponentially increasing delays."""
        client = _make_client(max_retries=3)
        sleep_calls = []

        with patch(
            "urllib.request.urlopen", side_effect=_http_error(502)
        ), patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
            with pytest.raises(CloudConnectionError):
                client.get_grading_config("cfg-1")

        # 3 retries → 3 sleep calls with delays 1, 2, 4
        assert sleep_calls == [1.0, 2.0, 4.0]

# ---------------------------------------------------------------------------
# Error handling — network errors (URLError)
# ---------------------------------------------------------------------------

class TestNetworkErrors:
    def test_url_error_retried(self):
        """Asserts network errors (URLError) are retried like 5xx responses."""
        client = _make_client(max_retries=2)
        network_err = urllib.error.URLError("Connection refused")

        with patch(
            "urllib.request.urlopen", side_effect=network_err
        ) as mock_open, patch("time.sleep"):
            with pytest.raises(CloudConnectionError):
                client.get_grading_config("cfg-1")

        assert mock_open.call_count == 3

    def test_url_error_error_message_does_not_leak_token(self):
        """Asserts the cloud token is not present in CloudConnectionError messages."""
        client = CloudClient("https://cloud.example.com", "leak-me-not", max_retries=0)
        network_err = urllib.error.URLError("timeout")

        with patch("urllib.request.urlopen", side_effect=network_err), patch(
            "time.sleep"
        ):
            with pytest.raises(CloudConnectionError) as exc_info:
                client.get_grading_config("cfg-1")

        assert "leak-me-not" not in str(exc_info.value)

    def test_succeeds_after_transient_network_error(self):
        """Asserts success is returned after a single transient URLError."""
        client = _make_client(max_retries=2)
        config = {"template_name": "html"}
        mock_resp = _mock_response(config)
        call_count = [0]

        def flaky(req, timeout=None):
            call_count[0] += 1
            if call_count[0] == 1:
                raise urllib.error.URLError("temporary")
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=flaky), patch("time.sleep"):
            result = client.get_grading_config("cfg-1")

        assert result == config

# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------

class TestJsonParsing:
    def test_invalid_json_raises_connection_error(self):
        """Asserts a malformed JSON response raises CloudConnectionError."""
        client = _make_client()
        mock_resp = _mock_response("not-json")

        with patch("urllib.request.urlopen", return_value=mock_resp), patch(
            "time.sleep"
        ):
            with pytest.raises(CloudConnectionError, match="invalid JSON"):
                client.get_grading_config("cfg-1")

    def test_empty_response_returns_empty_dict(self):
        """Asserts an empty response body returns {}."""
        client = _make_client()
        mock_resp = _mock_response("   ")

        with patch("urllib.request.urlopen", return_value=mock_resp), patch(
            "time.sleep"
        ):
            result = client.get_grading_config("cfg-1")

        assert result == {}
