"""GitHub integration plugin for Wondoner."""

from typing import Dict, Any, Optional, AsyncGenerator, ClassVar, List, Tuple

# Import interface and standard models
from wondoner.interfaces import TaskSourceIntegration, StandardTask

# Import local client and mapping functions
from .client import GitHubApiClient
from .mapping import map_github_issue_to_standard_task, map_standard_changes_to_github_payload


# --- Helper Function (moved parsing here as it's closely tied to plugin input) ---

def _parse_source_id(source_task_id: str) -> Tuple[str, str, int]:
    """Parses 'owner/repo/issue_number' into parts."""
    try:
        # Handle potential leading/trailing slashes if necessary
        source_task_id = source_task_id.strip('/')
        owner, repo, number_str = source_task_id.split('/')
        number = int(number_str)
        if not owner or not repo or number <= 0:
            raise ValueError("Invalid components")
        return owner, repo, number
    except (ValueError, IndexError, TypeError) as e:
        raise ValueError(
            f"Invalid GitHub source_task_id format: '{source_task_id}'. Expected 'owner/repo/number'.") from e


# --- Plugin Class ---

class GitHubPlugin(TaskSourceIntegration):
    """Wondoner integration plugin for GitHub Issues."""
    SOURCE_NAME: ClassVar[str] = "github"

    def __init__(self, config: Dict[str, Any]):
        """Initializes the GitHub plugin and its API client."""
        super().__init__(config)
        github_token = config.get('github_token')
        if not github_token:
            raise ValueError("GitHub token ('github_token') not found in config.")

        # Store config needed later, e.g., list of repos to monitor
        self.repositories_to_poll: List[str] = config.get('repositories', [])

        # Instantiate the API client
        self.client = GitHubApiClient(token=github_token)

    # Note: If the core app manages client lifecycle, __aenter__/__aexit__ might not be needed here.
    # Assuming the plugin manages its own client lifecycle for simplicity here.
    async def close_client(self):
        """Allow explicit closing if not using context manager."""
        await self.client.close()

    # --- Interface Methods Implementation ---

    async def get_task(self, source_task_id: str) -> Optional[StandardTask]:
        """Fetches a single GitHub issue and maps it."""
        try:
            owner, repo, issue_number = _parse_source_id(source_task_id)
            issue_data = await self.client.get_issue(owner, repo, issue_number)
            if issue_data:
                return map_github_issue_to_standard_task(issue_data, owner, repo)
            return None
        except ValueError as e:  # Catch parsing errors
            print(f"Error parsing source ID for get_task: {e}")
            return None
        except Exception as e:
            # Catch potential client errors if not handled inside client
            print(f"Error fetching task {source_task_id} via client: {e}")
            # Decide if specific client errors should return None or re-raise
            raise

    async def update_task(self, source_task_id: str, changes: Dict[str, Any]) -> StandardTask:
        """Updates a GitHub issue based on standard changes."""
        try:
            owner, repo, issue_number = _parse_source_id(source_task_id)
            payload = map_standard_changes_to_github_payload(changes)

            if not payload:
                # If no mappable changes, just fetch and return current state
                current_task = await self.get_task(source_task_id)
                if current_task is None:
                    # Raise error if task doesn't exist when trying to update with no changes
                    raise ValueError(f"Task {source_task_id} not found in GitHub for update.")
                return current_task

            updated_issue_data = await self.client.update_issue(owner, repo, issue_number, payload)
            return map_github_issue_to_standard_task(updated_issue_data, owner, repo)
        except ValueError as e:  # Catch parsing or not-found errors
            print(f"Error processing update for {source_task_id}: {e}")
            raise  # Re-raise value errors (like not found or bad ID)
        except Exception as e:
            # Catch potential client errors
            print(f"Error updating task {source_task_id} via client: {e}")
            raise

    async def poll_changes(self, last_sync_state: Optional[Any]) -> AsyncGenerator[StandardTask, None]:
        since_timestamp = str(last_sync_state) if last_sync_state else None

        for repo_full_name in self.repositories_to_poll:
            try:
                owner, repo = repo_full_name.split('/', 1)
                print(f"GitHub poll: Checking repo {owner}/{repo} since {since_timestamp or 'beginning'}")

                # THIS is the key part - make sure we're correctly awaiting the generator
                async_generator = self.client.list_updated_issues(owner, repo, since=since_timestamp)
                async for issue_data in async_generator:
                    try:
                        task = map_github_issue_to_standard_task(issue_data, owner, repo)
                        yield task
                    except Exception as map_err:
                        issue_num = issue_data.get('number', 'N/A')
                        print(f"Error mapping GitHub issue {owner}/{repo}#{issue_num}: {map_err}")

            except ValueError:  # Catch bad repo name format
                print(f"GitHub poll: Invalid repository name format in config: '{repo_full_name}'")
            except Exception as poll_err:
                # Log errors during polling a specific repo but continue to next repo
                print(f"Error polling GitHub repository {repo_full_name}: {poll_err}")

        print(f"GitHub poll: Finished polling repos.")
        # The core app should record the time this poll finished as the next state

    # parse_webhook_payload remains default (raise NotImplementedError)
