#!/usr/bin/env python3
"""github-pr-starter: turns a GitHub pull request URL into a Work origin.

Protocol (specs/005-plugin-origins/contracts/starter-protocol.md):
  stdin  {"arg": "https://github.com/<owner>/<repo>/pull/<n>"}
  stdout {"repository": {...}, "base_branch": "<head branch>",
          "start_modes": ["contribution", "fork"]}

`base_branch` is the PR's head branch: in contribution mode it is the branch
to check out, in fork mode the branch the new Work starts from. The repository
is identified by the *head* repo's fetch URL when the PR comes from a fork
(that is where the branch lives), otherwise the base repo's.
"""
import json
import os
import re
import subprocess
import sys
import urllib.request

PR_RE = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/pull/(\d+)/?$")


def fail(msg):
    print(f"github-pr-starter: {msg}", file=sys.stderr)
    sys.exit(1)


def fetch_pr(owner, repo, number):
    endpoint = f"repos/{owner}/{repo}/pulls/{number}"
    try:
        out = subprocess.run(
            ["gh", "api", endpoint], capture_output=True, text=True, check=True
        ).stdout
        return json.loads(out)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass  # gh missing or unauthenticated: try the public REST API

    req = urllib.request.Request(
        f"https://api.github.com/{endpoint}",
        headers={"Accept": "application/vnd.github+json"},
    )
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.load(resp)
    except Exception as exc:
        fail(f"could not fetch pull request {owner}/{repo}#{number}: {exc}")


def main():
    try:
        arg = json.load(sys.stdin).get("arg", "").strip()
    except (json.JSONDecodeError, AttributeError):
        fail("invalid input: not a JSON object")

    m = PR_RE.match(arg)
    if not m:
        fail(f"not a GitHub pull request URL: {arg!r}")
    owner, repo, number = m.groups()

    pr = fetch_pr(owner, repo, number)
    head = pr.get("head") or {}
    head_repo = head.get("repo")
    branch = head.get("ref")
    if not branch:
        fail("pull request has no head branch")
    if not head_repo:
        fail("head repository was deleted; the branch is no longer available")

    json.dump(
        {
            "repository": {
                "git_fetch_urls": [head_repo["clone_url"]],
                "name": head_repo["name"],
            },
            "base_branch": branch,
            "start_modes": ["contribution", "fork"],
        },
        sys.stdout,
    )
    print()


if __name__ == "__main__":
    main()
