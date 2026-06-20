import json
import subprocess
from dataclasses import dataclass, field
from typing import Any, Optional


def _run_gh(args: list[str], check: bool = True, repo: Optional[str] = None) -> subprocess.CompletedProcess:
    cmd = ["gh"] + args
    if repo:
        cmd.extend(["--repo", repo])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {result.stderr.strip()}")
    return result


@dataclass
class Issue:
    number: int
    title: str
    body: str
    state: str
    url: str
    labels: list[str] = field(default_factory=list)
    assignees: list[str] = field(default_factory=list)
    milestone: Optional[str] = None


@dataclass
class PullRequest:
    number: int
    title: str
    body: str
    state: str
    url: str
    head: str
    base: str
    mergeable: bool
    is_draft: bool = False
    labels: list[str] = field(default_factory=list)


@dataclass
class PRReview:
    state: str
    author: str
    body: str


class GitHubClient:
    def __init__(self, repo: Optional[str] = None, working_dir: Optional[str] = None):
        self.repo = repo
        self.working_dir = working_dir

    def _run(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        cmd = ["gh"] + args
        if self.repo:
            cmd.extend(["--repo", self.repo])
        kwargs = {"capture_output": True, "text": True}
        if self.working_dir:
            kwargs["cwd"] = self.working_dir
        result = subprocess.run(cmd, **kwargs)
        if check and result.returncode != 0:
            raise RuntimeError(f"gh {' '.join(args)} failed: {result.stderr.strip()}")
        return result

    def view_issue(self, number: int) -> Issue:
        result = self._run(["issue", "view", str(number), "--json", "number,title,body,state,url,labels,assignees,milestone"])
        data = json.loads(result.stdout)
        labels = [l["name"] for l in data.get("labels", [])]
        assignees = [a["login"] for a in data.get("assignees", [])]
        milestone = data.get("milestone", {}).get("title") if data.get("milestone") else None
        return Issue(
            number=data["number"], title=data["title"],
            body=data.get("body", ""), state=data["state"],
            url=data["url"], labels=labels, assignees=assignees, milestone=milestone,
        )

    def list_issues(self, state: str = "open", labels: Optional[list[str]] = None,
                    assignee: Optional[str] = None, author: Optional[str] = None,
                    limit: int = 30) -> list[Issue]:
        args = ["issue", "list", "--state", state, "--limit", str(limit),
                "--json", "number,title,body,state,url,labels,assignees,milestone"]
        if labels:
            args.extend(["--label", ",".join(labels)])
        if assignee:
            args.extend(["--assignee", assignee])
        if author:
            args.extend(["--author", author])
        result = self._run(args)
        issues = []
        for data in json.loads(result.stdout):
            labels = [l["name"] for l in data.get("labels", [])]
            assignees = [a["login"] for a in data.get("assignees", [])]
            milestone = data.get("milestone", {}).get("title") if data.get("milestone") else None
            issues.append(Issue(
                number=data["number"], title=data["title"],
                body=data.get("body", ""), state=data["state"],
                url=data["url"], labels=labels, assignees=assignees, milestone=milestone,
            ))
        return issues

    def create_issue(self, title: str, body: str, labels: Optional[list[str]] = None,
                     assignee: Optional[str] = None, milestone: Optional[str] = None) -> Issue:
        args = ["issue", "create", "--title", title, "--body", body]
        if labels:
            args.extend(["--label", ",".join(labels)])
        if assignee:
            args.extend(["--assignee", assignee])
        if milestone:
            args.extend(["--milestone", milestone])
        result = self._run(args)
        url = result.stdout.strip()
        number = int(url.strip("/").split("/")[-1])
        return self.view_issue(number)

    def edit_issue(self, number: int, title: Optional[str] = None, body: Optional[str] = None,
                   labels: Optional[list[str]] = None, state: Optional[str] = None) -> Issue:
        args = ["issue", "edit", str(number)]
        if title:
            args.extend(["--title", title])
        if body:
            args.extend(["--body", body])
        if labels:
            args.extend(["--add-label", ",".join(labels)])
        if state:
            args.extend(["--state", state])
        self._run(args)
        return self.view_issue(number)

    def close_issue(self, number: int) -> Issue:
        self._run(["issue", "close", str(number)])
        return self.view_issue(number)

    def view_pr(self, number: int) -> PullRequest:
        result = self._run(["pr", "view", str(number), "--json", "number,title,body,state,url,head,base,mergeable,isDraft,labels"])
        data = json.loads(result.stdout)
        labels = [l["name"] for l in data.get("labels", [])]
        return PullRequest(
            number=data["number"], title=data["title"],
            body=data.get("body", ""), state=data["state"],
            url=data["url"], head=data["headRefName"],
            base=data["baseRefName"], mergeable=data.get("mergeable", False),
            is_draft=data.get("isDraft", False), labels=labels,
        )

    def create_pr(self, title: str, body: str, head: str, base: str = "main",
                  draft: bool = False, labels: Optional[list[str]] = None) -> PullRequest:
        args = ["pr", "create", "--title", title, "--body", body, "--head", head, "--base", base]
        if draft:
            args.append("--draft")
        if labels:
            args.extend(["--label", ",".join(labels)])
        result = self._run(args)
        url = result.stdout.strip()
        number = int(url.strip("/").split("/")[-1])
        return self.view_pr(number)

    def list_prs(self, state: str = "open", base: Optional[str] = None,
                 head: Optional[str] = None, limit: int = 30) -> list[PullRequest]:
        args = ["pr", "list", "--state", state, "--limit", str(limit),
                "--json", "number,title,body,state,url,head,base,mergeable,isDraft,labels"]
        if base:
            args.extend(["--base", base])
        if head:
            args.extend(["--head", head])
        result = self._run(args)
        prs = []
        for data in json.loads(result.stdout):
            labels = [l["name"] for l in data.get("labels", [])]
            prs.append(PullRequest(
                number=data["number"], title=data["title"],
                body=data.get("body", ""), state=data["state"],
                url=data["url"], head=data["headRefName"],
                base=data["baseRefName"], mergeable=data.get("mergeable", False),
                is_draft=data.get("isDraft", False), labels=labels,
            ))
        return prs

    def merge_pr(self, number: int, method: str = "squash", delete_branch: bool = True) -> None:
        args = ["pr", "merge", str(number), f"--{method}"]
        if delete_branch:
            args.append("--delete-branch")
        self._run(args)

    def get_pr_checks(self, number: int) -> list[dict]:
        result = self._run(["pr", "checks", str(number), "--json", "name,state,conclusion"], check=False)
        if result.returncode != 0:
            return []
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return []

    def add_pr_comment(self, number: int, body: str) -> None:
        self._run(["pr", "comment", str(number), "--body", body])

    def add_issue_comment(self, number: int, body: str) -> None:
        self._run(["issue", "comment", str(number), "--body", body])
