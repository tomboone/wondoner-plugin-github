"""API client for GitHub integration."""

import httpx
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator

# Define base URL for GitHub API
GITHUB_API_BASE_URL = "https://api.github.com"


class GitHubApiClient:
    """A simple async client for interacting with the GitHub REST API v3."""

    def __init__(self, token: str, base_url: str = GITHUB_API_BASE_URL):
        if not token:
            raise ValueError("GitHub API token is required.")

        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        # Consider adding a timeout configuration
        self._client = httpx.AsyncClient(
            headers=self._headers,
            base_url=base_url,
            follow_redirects=True,
            timeout=30.0  # Example timeout
        )

    async def get_issue(self, owner: str, repo: str, issue_number: int) -> Optional[Dict[str, Any]]:
        """Fetches a single issue by owner, repo, and number."""
        url = f"/repos/{owner}/{repo}/issues/{issue_number}"
        try:
            response = await self._client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()  # Raise other HTTP errors
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"GitHub API error getting issue {owner}/{repo}#{issue_number}: {e.response.status_code}")
            # Log response body if needed: print(e.response.text)
            if e.response.status_code == 404:
                return None
            raise  # Re-raise other errors
        except Exception as e:
            print(f"Unexpected error getting issue {owner}/{repo}#{issue_number}: {e}")
            raise

    async def update_issue(self, owner: str, repo: str, issue_number: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Updates an issue using a PATCH request."""
        url = f"/repos/{owner}/{repo}/issues/{issue_number}"
        try:
            response = await self._client.patch(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"GitHub API error updating issue {owner}/{repo}#{issue_number}: {e.response.status_code}")
            # Log response body if needed: print(e.response.text)
            raise  # Re-raise other errors
        except Exception as e:
            print(f"Unexpected error updating issue {owner}/{repo}#{issue_number}: {e}")
            raise

    async def list_updated_issues(
            self, owner: str, repo: str, since: Optional[str] = None, state: str = "all"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Lists issues for a repo, optionally updated since a timestamp, handling pagination."""
        url = f"/repos/{owner}/{repo}/issues"
        params = {
            "state": state,
            "sort": "updated",
            "direction": "asc",  # Process oldest first to maintain order if stopped/restarted
            "per_page": 100,
        }
        if since:
            params["since"] = since  # ISO 8601 format timestamp string

        current_url: Optional[str] = url  # Use Optional[str] to satisfy type checkers

        while current_url:
            try:
                response = await self._client.get(current_url, params=params)
                response.raise_for_status()
                issues = response.json()

                if not issues:
                    break

                for issue in issues:
                    # Ignore pull requests if they appear in issues list
                    if 'pull_request' not in issue:
                        yield issue

                # Handle pagination using GitHub's Link header
                next_link = response.links.get("next")
                current_url = next_link["url"] if next_link else None
                params = None  # Params only needed for the first request

                if current_url:
                    # Optional: Small delay to avoid hitting rate limits aggressively
                    await asyncio.sleep(0.1)

            except httpx.HTTPStatusError as e:
                print(f"GitHub API error listing issues for {owner}/{repo}: {e.response.status_code}")
                # Log response body if needed: print(e.response.text)
                # Decide how to handle: stop iterating this repo? raise? log and continue?
                current_url = None  # Stop iterating this repo on error
                # Optionally re-raise if needed: raise
            except Exception as e:
                print(f"Unexpected error listing issues for {owner}/{repo}: {e}")
                current_url = None  # Stop iterating this repo on error
                # Optionally re-raise if needed: raise

    async def close(self):
        """Closes the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self):
        """Enter async context."""
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        await self._client.__aexit__(exc_type, exc_val, exc_tb)
