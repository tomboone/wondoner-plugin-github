"""Tests for GitHub integration client."""

import pytest
import httpx
import respx  # For mocking httpx requests
from typing import Dict, Any, AsyncIterator
from unittest.mock import AsyncMock

# Import the class to test (adjust path if needed)
from wondoner.plugin_github.client import GitHubApiClient, GITHUB_API_BASE_URL

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio


# --- Fixtures ---

@pytest.fixture
def api_token() -> str:
    """Provides a dummy API token."""
    return "dummy_github_token_123"


@pytest.fixture
async def api_client(api_token: str) -> AsyncIterator[GitHubApiClient]:
    """Provides an instance of GitHubApiClient for testing."""
    client = GitHubApiClient(token=api_token)
    # Yield the client so __aexit__ is called for cleanup if used as context manager
    yield client
    # Ensure client is closed after test
    await client.close()


@pytest.fixture
def sample_issue_json() -> Dict[str, Any]:
    """Sample raw JSON response for a single GitHub issue."""
    return {
        "number": 42, "title": "Test Issue from Client", "state": "open",
        "html_url": "https://example.com/gh/owner/repo/42", "created_at": "2024-02-01T10:00:00Z",
        "updated_at": "2024-02-02T11:00:00Z", "body": "Client test body",
        # Add other fields as needed for mapping tests elsewhere
    }


# --- Tests ---

def test_client_init_requires_token():
    """Test that initialization fails without a token."""
    with pytest.raises(ValueError, match="GitHub API token is required"):
        GitHubApiClient(token="")
    with pytest.raises(ValueError, match="GitHub API token is required"):
        GitHubApiClient(token=None)  # type: ignore


@respx.mock
async def test_client_init_headers(api_token: str):
    """Test that the client initializes with correct auth headers."""
    # Define a dummy route for any GET request to check headers
    route = respx.get(f"{GITHUB_API_BASE_URL}/").respond(json={})

    async with GitHubApiClient(token=api_token) as client:
        # Make a dummy request to ensure headers are sent
        await client._client.get("/")  # Access underlying httpx client

    # Assert the route was called and check the request headers
    assert route.called
    request = route.calls[0].request
    assert request.headers["Authorization"] == f"Bearer {api_token}"
    assert request.headers["Accept"] == "application/vnd.github.v3+json"
    assert request.headers["X-GitHub-Api-Version"] == "2022-11-28"


@respx.mock
async def test_get_issue_success(api_client: GitHubApiClient, sample_issue_json: Dict[str, Any]):
    """Test fetching an issue successfully."""
    owner, repo, num = "testorg", "testrepo", 42
    expected_url = f"{api_client._client.base_url}/repos/{owner}/{repo}/issues/{num}"
    route = respx.get(expected_url).respond(json=sample_issue_json)

    result = await api_client.get_issue(owner, repo, num)

    assert route.called
    assert result == sample_issue_json


@respx.mock
async def test_get_issue_not_found(api_client: GitHubApiClient):
    """Test fetching an issue that doesn't exist (404)."""
    owner, repo, num = "testorg", "testrepo", 404
    expected_url = f"{api_client._client.base_url}/repos/{owner}/{repo}/issues/{num}"
    route = respx.get(expected_url).respond(404)

    result = await api_client.get_issue(owner, repo, num)

    assert route.called
    assert result is None


@respx.mock
async def test_get_issue_other_error(api_client: GitHubApiClient):
    """Test fetching an issue when a non-404 HTTP error occurs."""
    owner, repo, num = "testorg", "testrepo", 500
    expected_url = f"{api_client._client.base_url}/repos/{owner}/{repo}/issues/{num}"
    route = respx.get(expected_url).respond(500, text="Server Error")

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await api_client.get_issue(owner, repo, num)

    assert route.called
    assert exc_info.value.response.status_code == 500


@respx.mock
async def test_update_issue_success(api_client: GitHubApiClient, sample_issue_json: Dict[str, Any]):
    """Test updating an issue successfully."""
    owner, repo, num = "testorg", "testrepo", 42
    expected_url = f"{api_client._client.base_url}/repos/{owner}/{repo}/issues/{num}"
    update_payload = {"title": "New Title", "state": "closed"}

    # Mock the PATCH request, checking the payload
    updated_response_json = sample_issue_json.copy()
    updated_response_json.update(update_payload)  # Simulate response reflecting changes
    route = respx.patch(expected_url, json=update_payload).respond(json=updated_response_json)

    result = await api_client.update_issue(owner, repo, num, update_payload)

    assert route.called
    # Check request payload (respx stores it)
    assert route.calls[0].request.content == b'{"title": "New Title", "state": "closed"}'
    assert result == updated_response_json


@respx.mock
async def test_update_issue_error(api_client: GitHubApiClient):
    """Test updating an issue when an HTTP error occurs."""
    owner, repo, num = "testorg", "testrepo", 422
    expected_url = f"{api_client._client.base_url}/repos/{owner}/{repo}/issues/{num}"
    update_payload = {"title": "Invalid Update"}
    route = respx.patch(expected_url).respond(422, text="Unprocessable Entity")

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await api_client.update_issue(owner, repo, num, update_payload)

    assert route.called
    assert exc_info.value.response.status_code == 422


@respx.mock
async def test_list_updated_issues_no_pagination(api_client: GitHubApiClient, sample_issue_json: Dict[str, Any]):
    """Test listing issues when only one page of results exists."""
    owner, repo = "testorg", "testrepo"
    since_ts = "2024-02-01T00:00:00Z"
    expected_url = f"{api_client._client.base_url}/repos/{owner}/{repo}/issues"
    # Note: respx matches params flexibly by default
    route = respx.get(expected_url, params={'since': since_ts}).respond(json=[sample_issue_json])

    results = [item async for item in api_client.list_updated_issues(owner, repo, since=since_ts)]

    assert route.called
    # Check specific params if needed: assert route.calls[0].request.url.params['since'] == since_ts
    assert len(results) == 1
    assert results[0] == sample_issue_json


@respx.mock
async def test_list_updated_issues_with_pagination(api_client: GitHubApiClient, sample_issue_json: Dict[str, Any]):
    """Test listing issues with multiple pages using Link header."""
    owner, repo = "paginated", "repo"
    since_ts = "2024-03-01T00:00:00Z"
    base_url = f"{api_client._client.base_url}/repos/{owner}/{repo}/issues"
    page2_url = f"{base_url}?state=all&sort=updated&direction=asc&per_page=100&page=2"  # Example next link

    issue_page1 = sample_issue_json.copy()
    issue_page2 = sample_issue_json.copy()
    issue_page2["number"] = 99
    issue_page2["title"] = "Issue on Page 2"

    # Mock page 1 response with a Link header pointing to page 2
    route1 = respx.get(url=base_url, params={'since': since_ts}).respond(json=[issue_page1], headers={
        "Link": f'<{page2_url}>; rel="next", <https://example.com/last>; rel="last"'})
    # Mock page 2 response with no Link header
    route2 = respx.get(url=page2_url).respond(json=[issue_page2], headers={})

    results = [item async for item in api_client.list_updated_issues(owner, repo, since=since_ts)]

    assert route1.called
    assert route2.called
    assert len(results) == 2
    assert results[0]["number"] == 42
    assert results[1]["number"] == 99


@respx.mock
async def test_list_updated_issues_error_during_pagination(
        api_client: GitHubApiClient,
        sample_issue_json: Dict[str, Any],
        # caplog # Use caplog if client uses logging instead of print
        # capsys # Use capsys if client uses print
):
    """Test listing issues when an error occurs on a subsequent page."""
    owner, repo = "error", "repo"
    # Define base URL for the issues endpoint
    issues_base_url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/issues"

    # Define parameters for the FIRST page request (matching client's defaults)
    params_page1 = {
        "state": "all",
        "sort": "updated",
        "direction": "asc",
        "per_page": 100,
        # 'since' is omitted as we call without it in this test case
    }

    # Define the EXACT URL for the second page (as it appears in Link header)
    # Ensure this matches precisely what your client extracts and requests
    page2_url = f"{issues_base_url}?page=2"  # Adjust if client adds other params

    # --- Mock Responses ---
    # Route 1: Matches ONLY the base URL + specific params for page 1
    route1 = respx.get(issues_base_url, params=params_page1).respond(json=[sample_issue_json],
                                                                     headers={"Link": f'<{page2_url}>; rel="next"'})

    # Route 2: Matches ONLY the exact URL for page 2, returns error
    route2 = respx.get(page2_url).respond(
        status_code=500,
        text="Internal Server Error simulation"
    )
    # --- End Mock Responses ---

    results = []
    # If client uses print for errors, capture it with capsys fixture
    # (add 'capsys' to test function args)
    # If client uses logging, capture with caplog fixture
    # (add 'caplog' to test function args and use 'with caplog.at_level(...)')
    async for item in api_client.list_updated_issues(owner, repo):  # Call without 'since'
        results.append(item)

    # --- Assertions ---
    assert route1.called, "Page 1 route was not called"
    assert route2.called, "Page 2 error route was not called"

    # Should only have the item(s) from page 1
    assert len(results) == 1
    assert results[0]["number"] == sample_issue_json["number"]

    # Optional: Assert that an error was logged or printed by the client
    # E.g., using capsys:
    # captured = capsys.readouterr()
    # assert f"GitHub API error listing issues for {owner}/{repo}" in captured.out
    # assert "500" in captured.out
    # E.g., using caplog:
    # assert f"GitHub API error listing issues for {owner}/{repo}" in caplog.text
    # assert "500" in caplog.text


async def test_client_context_manager(api_token: str, mocker):
    """Test the async context manager calls close."""
    # Mock the underlying client's methods
    mock_httpx_client = AsyncMock()
    mock_httpx_client.aclose = AsyncMock()
    mock_httpx_client.__aenter__ = AsyncMock(return_value=mock_httpx_client)
    mock_httpx_client.__aexit__ = AsyncMock()

    # Patch httpx.AsyncClient to return our mock
    mocker.patch('httpx.AsyncClient', return_value=mock_httpx_client)

    async with GitHubApiClient(token=api_token) as client:
        assert isinstance(client, GitHubApiClient)
        # Optionally make a dummy call if needed within context
        # await client.get_issue("a", "b", 1)

    # Assert that the underlying client's context methods were called
    mock_httpx_client.__aenter__.assert_awaited_once()
    mock_httpx_client.__aexit__.assert_awaited_once()
    # Note: Testing aclose directly might be redundant if __aexit__ handles it,
    # but we can test the explicit close method too.
    # mock_httpx_client.aclose.assert_awaited_once() # This won't be called by context manager exit usually


async def test_client_explicit_close(api_token: str, mocker):
    """Test the explicit close method."""
    mock_httpx_client = AsyncMock()
    mock_httpx_client.aclose = AsyncMock()
    mocker.patch('httpx.AsyncClient', return_value=mock_httpx_client)

    client = GitHubApiClient(token=api_token)
    await client.close()

    mock_httpx_client.aclose.assert_awaited_once()
