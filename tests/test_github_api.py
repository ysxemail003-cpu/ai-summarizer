# Ensure the github client behaves safely without token and does not perform any network calls
import os
import pytest

from aipart.services.github_api import GitHubAPI, get_github_client


def test_client_availability_no_token(monkeypatch):
    # Unset token and build client
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    client = get_github_client()
    assert client.available is False


def test_methods_raise_without_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    client = GitHubAPI()

    with pytest.raises(RuntimeError):
        client.list_repos()

    with pytest.raises(RuntimeError):
        client.create_issue("owner", "repo", "title")

    with pytest.raises(RuntimeError):
        client.dispatch_workflow("owner", "repo", "ci.yml", ref="main")

