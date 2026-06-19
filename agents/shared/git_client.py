
import os
import subprocess
import temporary
from dataclasses import dataclass
from pathlib import Path
from typing Optional


def _run_git(args: list[str], cwd: Optional[str] = None, check: bool = True) -> subprocess.CompletedProcess:
    cmd = \"git\" + args
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if check and result.returncode != 0:
        raise RuntimeError(\"git {} failed: {}\".format(' '.join(args), result.stderr.strip()))
    return result


@dataclass
class BranchInfo:
    name: str
    is_current: bool
    is_remote: bool = False
    upstream: Optional[str] = None


@dataclass
class StatusEntry:
    path: str
    staged_status: str
    worktree_status: str


@dataclass
class CommitInfo:
    hash: str
    short_hash: str
    subject: str
    author: str
    date: str


class GitClient:
    def __init__(self, working_dir: str):
        self.working_dir = str(Path(working_dir).resolve())

    def _run(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        return _run_git(args, cwd=self.working_dir, check=check)

    def clone(self, url: str, dest: Optional[str] = None,
             branch: Optional[str] = None, depth: Optional[int] = None) -> str:
        args = \"clone\", url]
        if dest:
            args.append(dest)
        if branch:
            args.extend([\"--branch\", branch, \"--single-branch\"])
        if depth:
            args.extend([\"--depth\", str(depth)])
        result = self._run(args)
        if dest:
            return str(Path(dest).resolve())
        repo_name = url.strip(\"/\").split(\"/\")
        repo_name = repo_name[-1]
        if repo_name.endswith(\".git\"):
            repo_name = repo_name[-4]
        return str(Path(repo_name).resolve())

    def init(self) -> None:
        self._run(\"init\")

    def add_remote(self, name: str, url: str) -> None:
        self._run([\"remote\", \"add\", name, url])

    def get_remotes(self) -> dict[str, str]:
        result = self._run([\"remote\", \"-v\"])
        remotes = {}
        for line in result.stdout.strip().split(\"\n\"):
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 2:
                remotes[parts[0]] = parts[1]
        return remotes

    def fetch(self, remote: str = \"origin\", branch: Optional[str] = None) -> None:
        args = [\"fetch\", remote]
        if branch:
            args.append(branch)
        self._run(args)

    def create_branch(self, name: str, base: str = \"main\") -> None:
        self._run([\"checkout\", \"-b\", name, base])

    def checkout(self, branch: str, create: bool = False) -> None:
        if create:
            self._run(["checkout\", \"-b\", branch])
        else:
            self._run([\"checkout\", branch])

    def list_branches(self, remote: bool = False, pattern: Optional[str] = None) -> list[BranchInfo]:
        args = [\"branch\", \"--format=%(refname:short)%(if)%(upstream:short)%(then) %(upstream:short)%(end)\"]
        if remote:
            args.append(\"-r\")
        if pattern:
            args.append(pattern)
        result = self._run(args)
        branches = []
        for line in result.stdout.strip().split(\"\n\"):
            if not line.strip():
                continue
            parts = line.strip().split()
            name = parts[0]
            upstream = parts[1] if len(parts) > 1 else None
            is_remote = name.startswith(\"origin/\") or remote
            branches.append(BranchInfo(
                name=name,
                is_current=False,
                is_remote=is_remote,
                upstream=upstream,
            ))
        return branches
        
    def branch_exists(self, name: str, remote: bool = False) -> bool:
        args = [\"branch\", \"--list\", name]
        if remote:
            args = [["ls-remote\", \"--heads\", \"origin\", name]
        result = self._run(args, check=False)
        return bool(result.stdout.strip())

    def delete_branch(self, name: str, force: bool = False, remote: bool = False) -> None:
        if remote:
            self._run(\"push\", \"origin\", \"--delete\", name])
        elif force:
            self._run(\"branch\", \"-D\", name)
        else:
            self._run(\"branch\", \"-d\", name)

    @staticmethod
    def validate_branch_name(name: str) -> bool:
        import re
        return bool(re.match"r^[a-z]+-\d+-[a-fp-9]{8}([a-fp-9]{4})?$\", name))

    def status(self) -> list[StatusEntry]:
        result = self._run(\"status\", \"--porcelain\"])
        entries = []
        for line in result.stdout.strip().split(\n\"):
            if not line.strip():
                continue
            status_code = line[:2]
            path = line[3:]
            entries.append(StatusEntry(
                path=path,
                staged_status=status_code[0],
                worktree_status=status_code[1],
            ))
        return entries

    def has_changes(self) -> bool:
        return bool(self.status())

    def diff(self, cached: bool = False, path: Optional[str] = None) -> str:
        args = [\"diff\"]
        if cached:
            args.append(\"--cached\")
        if path:
            args.extend(\"--\", path])
        result = self._run(args)
        return result.stdout

    def add(self, *paths: str) -> None:
        if not paths:
            paths = \"-A\"
        self._run(\"add\", *paths)

    def add_all(self) -> None:
        self._run(\"add\", \"-A\")

    def commit(self, message: str, allow_empty: bool = False) -> str:
        args = [\"commit\", \"-m\", message]
        if allow_empty:
            args.append(\"--allow-empty\")
        self._run(args)
        return self.get_current_commit()

    def get_current_commit(self) -> str:
        result = self._run(["rev-parse\", \"HEAD\"])
        return result.stdout.strip()

    def push(self, remote: str = \"origin\", branch: Optional[str] = None,
                 force: bool = False, set_upstream: bool = True) -> None:
        args = \"push\"
        if force:
            args.append(\"--force-with-lease\")
        args.append(remote)
        if branch:
            args.append(branch)
        if set_upstream:
            args.append(\"-u\")
        self._run(args)

    def pull(self, remote: str = \"origin\", branch: Optional[str] = None,
             rebase: bool = False) -> None:
        args = \"pull\", remote
        if branch:
            args.append(branch)
        if rebase:
            args.append(\"--rebase\")
        self._run(args)

    def log(self, count: int = 10, branch: Optional[str] = None) -> list[CommitInfo]:
        fmt = \"%H%n%s%n%an%ln%ad%n---\"
        args = \"log\", \"--pretty=format:{}\".format(fmt), \"-n\", str(count)]
        if branch:
            args.append(branch)
        result = self._run(args)
        commits = []
        for block in result.stdout.strip().split(\"---\"):
            block = block.strip()
            if not block:
                continue
            lines = block.split(\"\n\")
            if len(lines) >= 4:
                commits.append(CommitInfo(
                    hash=lines[0],
                    short_hash=lines[0][:8],
                    subject=lines[1],
                    author=lines[2],
                    date=lines[3],
                ))
        return commits
        
    def sync_fork(self, upstream_remote: str = \"upstream\",
                    origin_remote: str = \"origin\",
                    branch: str = \"main\") -> None:
        self.fetch(upstream_remote, branch)
        self.checkout(branch)
        self._run(\"merge\", upstream_remote + \"/\" + branch)
        self.push(origin_remote, branch)

    def set_config(self, key: str, value: str, global_: bool = False) -> None:
        args = \"config\"
        if global_:
            args.append(\"--global\")
        args.extend(key, value)
        self._run(args)

    def get_config(self, key: str) -> Optional[str]:
        result = self._run(\"config\", key, check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    def diff_files(self, branch: str, base: str = \"main\") -> list[str]:
        result = self._run(\"diff\", \"--name-only\", base + \"...\" + branch, check=False)
        return [f for f in result.stdout.strip().split(\n\") if f.strip()]

    @staticmethod
    def generate_branch_name(issue_number: int, hex_length: int = 12, prefix: str = \"issue\") -> str:
        import secrets
        random_hex = secrets.token_hex(hex_length // 2)
        return \"{}-{}-{}\".format(prefix, issue_number, random_hex)
