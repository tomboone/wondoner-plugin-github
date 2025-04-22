"""Tests for GitHub integration mapping functions."""

from datetime import datetime, timezone, date

import pytest

# Assuming interfaces package is installed
from wondoner.interfaces import StandardTask, TaskStatus

# Import functions to test (adjust path if needed)
from wondoner.plugin_github.mapping import (
    map_github_issue_to_standard_task,
    map_standard_changes_to_github_payload,
)


# --- Fixtures ---

@pytest.fixture
def sample_github_issue_open() -> dict:
    """Provides a sample raw GitHub issue dictionary (open state)."""
    return {
        "number": 123,
        "title": "Test Issue Title",
        "body": "This is the description.\nIt has multiple lines.",
        "state": "open",
        "html_url": "https://github.com/test-owner/test-repo/issues/123",
        "created_at": "2024-01-10T10:00:00Z",
        "updated_at": "2024-01-11T11:30:00Z",
        "closed_at": None,
        "user": {"login": "testuser"},
        "assignee": None,
        "assignees": [],
        "labels": [],
        "milestone": None,
        # Add other fields GitHub might return
    }


# tests/test_mapping.py

@pytest.fixture
def sample_github_issue_closed(sample_github_issue_open: dict) -> dict:  # Request fixture as argument
    """Provides a sample raw GitHub issue dictionary (closed state)."""
    # Use the *argument* sample_github_issue_open, not call the function
    issue = sample_github_issue_open.copy()  # Copy to avoid modifying the yielded dict
    issue.update({
        "state": "closed",
        "closed_at": "2024-01-12T12:00:00Z",
        "closed_by": {"login": "anotheruser"},
    })
    return issue


# --- Tests for map_github_issue_to_standard_task ---

def test_map_github_issue_open(sample_github_issue_open):
    """Test mapping an open GitHub issue."""
    owner = "test-owner"
    repo = "test-repo"
    issue_data = sample_github_issue_open
    task = map_github_issue_to_standard_task(issue_data, owner, repo)

    assert isinstance(task, StandardTask)
    assert task.source_id == f"{owner}/{repo}/{issue_data['number']}"
    assert task.source_name == "github"
    assert task.name == issue_data['title']
    assert task.description == issue_data['body']
    assert task.status == TaskStatus.NOT_DONE
    assert task.url == issue_data['html_url']
    assert task.due_date is None  # No mapping for due date yet
    assert task.created_at == datetime(2024, 1, 10, 10, tzinfo=timezone.utc)
    assert task.updated_at == datetime(2024, 1, 11, 11, 30, tzinfo=timezone.utc)
    assert task.raw_data == issue_data
    # Aggregator fields should be empty/default initially
    assert task.id == ""
    assert task.project_id == ""


def test_map_github_issue_closed(sample_github_issue_closed):
    """Test mapping a closed GitHub issue."""
    owner = "test-owner"
    repo = "test-repo"
    issue_data = sample_github_issue_closed
    task = map_github_issue_to_standard_task(issue_data, owner, repo)

    assert task.status == TaskStatus.DONE
    assert task.updated_at == datetime(2024, 1, 11, 11, 30, tzinfo=timezone.utc)


def test_map_github_issue_minimal_data():
    """Test mapping with minimal required fields from GitHub."""
    owner = "min-owner"
    repo = "min-repo"
    issue_data = {
        "number": 1,
        "title": "Minimal",
        "state": "open",
        # Missing body, url, timestamps etc.
    }
    task = map_github_issue_to_standard_task(issue_data, owner, repo)

    assert task.source_id == f"{owner}/{repo}/1"
    assert task.name == "Minimal"
    assert task.description is None
    assert task.status == TaskStatus.NOT_DONE
    assert task.url is None
    assert task.created_at is None
    assert task.updated_at is None
    assert task.raw_data == issue_data


def test_map_github_issue_null_body(sample_github_issue_open):
    """Test mapping when GitHub issue body is explicitly null."""
    owner = "test-owner"
    repo = "test-repo"
    issue_data = sample_github_issue_open
    issue_data["body"] = None
    task = map_github_issue_to_standard_task(issue_data, owner, repo)
    assert task.description is None


def test_map_github_issue_missing_number():
    """Test error handling when issue number is missing."""
    with pytest.raises(ValueError, match="GitHub issue payload missing 'number'"):
        map_github_issue_to_standard_task({"title": "No number"}, "o", "r")


def test_map_github_issue_empty_payload():
    """Test error handling for empty payload."""
    with pytest.raises(ValueError, match="Cannot map empty GitHub issue payload"):
        map_github_issue_to_standard_task({}, "o", "r")


# --- Tests for map_standard_changes_to_github_payload ---

def test_map_changes_name():
    """Test mapping a name change."""
    changes = {"name": "New Title"}
    payload = map_standard_changes_to_github_payload(changes)
    assert payload == {"title": "New Title"}


def test_map_changes_description():
    """Test mapping a description change."""
    changes = {"description": "New Body"}
    payload = map_standard_changes_to_github_payload(changes)
    assert payload == {"body": "New Body"}


def test_map_changes_status_to_done():
    """Test mapping status change to DONE."""
    changes = {"status": TaskStatus.DONE}
    payload = map_standard_changes_to_github_payload(changes)
    assert payload == {"state": "closed"}


def test_map_changes_status_to_not_done():
    """Test mapping status change to NOT_DONE."""
    changes = {"status": TaskStatus.NOT_DONE}
    payload = map_standard_changes_to_github_payload(changes)
    assert payload == {"state": "open"}


def test_map_changes_multiple():
    """Test mapping multiple changes."""
    changes = {"name": "Updated Title", "status": TaskStatus.DONE}
    payload = map_standard_changes_to_github_payload(changes)
    assert payload == {"title": "Updated Title", "state": "closed"}


def test_map_changes_empty():
    """Test mapping an empty changes dictionary."""
    changes = {}
    payload = map_standard_changes_to_github_payload(changes)
    assert payload == {}


def test_map_changes_unmapped_fields():
    """Test that unmapped fields in changes are ignored."""
    changes = {"name": "A Name", "due_date": date(2025, 5, 1), "custom": "value"}
    payload = map_standard_changes_to_github_payload(changes)
    # Only 'name' should map to 'title'
    assert payload == {"title": "A Name"}
