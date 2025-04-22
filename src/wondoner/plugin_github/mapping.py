"""Mapping functions for GitHub integration."""

from datetime import datetime
from typing import Dict, Any

# Assuming interfaces is installed and accessible
from wondoner.interfaces import StandardTask, TaskStatus


def map_github_issue_to_standard_task(
        issue_payload: Dict[str, Any], owner: str, repo: str
) -> StandardTask:
    """Maps a GitHub Issue API response dictionary to a StandardTask dataclass."""
    if not issue_payload:
        raise ValueError("Cannot map empty GitHub issue payload.")

    issue_number = issue_payload.get('number')
    if not issue_number:
        raise ValueError("GitHub issue payload missing 'number'.")

    source_id = f"{owner}/{repo}/{issue_number}"
    status = TaskStatus.DONE if issue_payload.get('state') == 'closed' else TaskStatus.NOT_DONE

    # GitHub issues don't have a native due date field in the main issue object
    # You might add logic later to parse from labels, milestones, body, or Project V2 items
    due_date = None

    # Ensure timestamps are timezone-aware (GitHub provides ISO 8601 UTC 'Z')
    created_at_str = issue_payload.get('created_at')
    updated_at_str = issue_payload.get('updated_at')

    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00')) if created_at_str else None
    updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00')) if updated_at_str else None

    # Note: We don't set aggregator 'id' or 'project_id' here.
    # The core app handles mapping the repo/source info to these fields.
    return StandardTask(
        id="",  # To be filled by core app
        project_id="",  # To be filled by core app
        # ---
        source_id=source_id,
        source_name="github",
        name=issue_payload.get('title', ''),
        description=issue_payload.get('body'),
        url=issue_payload.get('html_url'),
        status=status,
        due_date=due_date,
        created_at=created_at,
        updated_at=updated_at,
        raw_data=issue_payload  # Store original payload
    )


def map_standard_changes_to_github_payload(changes: Dict[str, Any]) -> Dict[str, Any]:
    """Maps a Wondoner standard 'changes' dictionary to a GitHub API PATCH payload."""
    payload = {}
    if 'name' in changes:
        payload['title'] = changes['name']
    # NOTE: Sending description will REPLACE the entire body.
    # Partial updates might require getting the body first if needed.
    if 'description' in changes:
        payload['body'] = changes['description']
    if 'status' in changes:
        # Map Wondoner status back to GitHub state
        payload['state'] = 'closed' if changes['status'] == TaskStatus.DONE else 'open'

    # Add other mappings here if needed (e.g., labels, assignee)
    # if 'assignee_id' in changes: payload['assignees'] = [changes['assignee_id']] # Example
    # if 'labels' in changes: payload['labels'] = changes['labels'] # Example (needs list of strings)

    # Note: Due date cannot be directly mapped to a standard issue field.

    return payload
