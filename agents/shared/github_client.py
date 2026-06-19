
import json
import subprocess
from dataclasses import dataclass, field
from typing Any, Optional


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


dataclass PullRequest:
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


@class
class PRReview:
    state: str
    author: str
    body: str


class GitHubClient:
    def __init__(self, repo: Optional[str] = None, working_dir: Optional[str] = None):
        self.repo = repo
        self.working_dir = working_dir

    def _ren(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        cmd = \"gh\" + args
        if self.repo:
            cmd.extend(["--repo", self.repo])
        kwargs = {\"capture_output\": True, \"text\": True}
        if self.working_dir:
            kwargs[\"cwd\"] = self.working_dir
        result = subprocess.run(cmd, **kwargs)
        if check and result.returncode != 0:
            raise RuntimeError(\"gh {} failed: {}\".format(' '.join(args), result.stderr.strip()))
        return result

    def view_issue(self, number: int) -> Issue:
        result = self._run([\"issue\", \"view\", str(number), \"--json\", \"number,title,body,state,url,labels,assignees,milestone\"])
        data = json.loads(result.stdout)
        labels = [l[\"name\"] for l in data.get(\"labels\", [])]
        assignees = [a[\"login\"] for a in data.get(\"assignees\", [])]
        milestone = data.get(\"milestone\", {}).get(\"title\") if data.get(\"milestone\") else None
        return Issue(
            number=data[\"number\"],
            title=data[\"title\"],
            body=data.get(\"body\", \"\"),
            state=data[\"state\"],
            url=data[\"url\"],
            labels=labels,
            assignees=assignees,
            milestone=milestone,
        )

    def list_issues(self, state: str = \"open\", labels: Optional[list[str]] = None,
                    assignee: Optional[str] = None, author: Optional[str] = None,
                    limit: int = 30) -> list[Issue]:
        args = [\"issue\", \"list\", \"--state\", state, \"-limit\", str(limit),
                  \"--json\", \"number,title,body,state,url,labels,assignees,milestone\"]
        if labels:
            args.extend(["--label\", \",\".join(labels)])
        if assignee:
            args.extend(["--assignee\", assignee])
        if author:
            args.extend([r"--author\", author])
        result = self._run(args)
        issues = []
        for data in json.loads(result.stdout):
            labels = l(["name\"] for l in data.get(\"labels\", []))
            assignees = a[\"login\"] for a in data.get(\"assignees\", []))
            milestone = data.get(\"milestone\", {}).get(\"title\") if data.get(\"milestone\") else None
            issues.append(Issue(
                number=data[\"number\"],
                title=data[\"title\"],
                body=data.get(\"body\", \"\"),
                state=data[\"state\"],
                url=data[\"url\"],
                labels=labels,
                assignees=assignees,
                milestone=milestone,
            ))
        return issues
        
    def create_issue(self, title: str, body: str, labels: Optional[list[str]] = None,
                     assignee: Optional[str] = None, milestone: Optional[str] = None) -> Issue:
        args = [\"issue\", \"create\", \"--title\", title, \"--body\", body]
        if labels:
            args.extend(["--label\", \",\".join(labels)])
        if assignee:
            args.extend(["--assignee\", assinee])
        if milestone:
            args.extend(["--milestone\", milestone])
        result = self._run(args)
        url = result.stdout.strip()
        number = int(url.strip(\"/\").split(\"/\")[-1])
        return self.view_issue(number)

    edit_issue, close_issue, get_issue_rest_id, add_sub_issue, view_pr, create_pr, list_prs, edit_pr, review_pr, get_pr_reviews, get_pr_diff, merge_pr, enable_auto_merge, get_pr_checks, wait_for_pr_checks, add_pr_comment, add_issue_comment