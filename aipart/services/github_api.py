import os
from typing import Any, Dict, List, Optional

import httpx


class GitHubAPI:
    """
    Minimal synchronous GitHub API client.

    - Reads token from env var GITHUB_TOKEN by default
    - Exposes `.available` to indicate whether token is present
    - Provides a few common operations (list repos, create issue, dispatch workflow)
    - Raises a clear error if methods are used without a token
    """

    def __init__(self, token: Optional[str] = None, base_url: str = "https://api.github.com") -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.available: bool = bool(self.token)
        # Always include version + accept; add auth only if token available
        self._headers: Dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            self._headers["Authorization"] = f"Bearer {self.token}"

    def _require_token(self) -> None:
        if not self.available:
            raise RuntimeError(
                "GITHUB_TOKEN is not set. Please set it in your environment before calling GitHub API."
            )

    def list_repos(self, per_page: int = 5) -> List[Dict[str, Any]]:
        """List the authenticated user's repositories (first page)."""
        self._require_token()
        url = f"{self.base_url}/user/repos"
        r = httpx.get(url, headers=self._headers, params={"per_page": per_page, "sort": "updated"}, timeout=30.0)
        r.raise_for_status()
        return r.json()

    def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str = "",
        labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create an issue in the given repo."""
        self._require_token()
        url = f"{self.base_url}/repos/{owner}/{repo}/issues"
        payload: Dict[str, Any] = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        r = httpx.post(url, headers=self._headers, json=payload, timeout=30.0)
        r.raise_for_status()
        return r.json()

    def dispatch_workflow(
        self,
        owner: str,
        repo: str,
        workflow_file: str,
        ref: str = "main",
        inputs: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Trigger a workflow_dispatch for a given workflow file name under .github/workflows/"""
        self._require_token()
        url = f"{self.base_url}/repos/{owner}/{repo}/actions/workflows/{workflow_file}/dispatches"
        payload: Dict[str, Any] = {"ref": ref}
        if inputs:
            payload["inputs"] = inputs
        r = httpx.post(url, headers=self._headers, json=payload, timeout=30.0)
        r.raise_for_status()
        return True

    def create_repo(
        self,
        name: str,
        private: bool = True,
        description: str = "",
        auto_init: bool = False,
        org: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a repository for the authenticated user, or under an organization if org provided."""
        self._require_token()
        if org:
            url = f"{self.base_url}/orgs/{org}/repos"
        else:
            url = f"{self.base_url}/user/repos"
        payload: Dict[str, Any] = {
            "name": name,
            "private": private,
            "description": description,
            "auto_init": auto_init,
        }
        r = httpx.post(url, headers=self._headers, json=payload, timeout=30.0)
        r.raise_for_status()
        return r.json()


def get_github_client(token: Optional[str] = None) -> GitHubAPI:
    """Factory to get a GitHubAPI client using env token by default."""
    return GitHubAPI(token=token)
