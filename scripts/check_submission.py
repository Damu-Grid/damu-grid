"""Pre-submission checks (DG-39). Run from the repository root before making the repo public:

    uv run python scripts/check_submission.py          # repository checks
    uv run python scripts/check_submission.py --tests  # also run pytest

Checks what is committed (HEAD), so Windows line-ending conversion in the working copy does not
cause false alarms: no .env file, no secret-looking strings, no file over 5 MB outside the two
data folders (data/raw/ and data/enhanced/, as in the CI), and every official CSV identical to
data/raw/SHA256SUMS. A git problem (no commit yet, a missing blob) is reported as a failure, not
as a traceback. Exits 1 if anything fails.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys

MAX_BYTES = 5 * 1024 * 1024
# Both data folders are exempt from the size limit and from the secret scan (the CI does the same).
DATA_DIRS = ("data/raw/", "data/enhanced/")
# The checker and its tests contain fake secret shapes on purpose.
SELF_FILES = {"scripts/check_submission.py", "tests/test_check_submission.py"}
SCANNED_SUFFIXES = (
    ".py", ".md", ".toml", ".json", ".yml", ".yaml", ".ts", ".tsx", ".js", ".txt", ".example",
    ".ini", ".cfg", ".sh", ".ipynb", ".csv",
)
SCANNED_NAMES = ("Dockerfile",)
SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key id
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),  # common LLM API key shape
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),  # GitHub token
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"\s]{12,}['\"]"),
]


class GitError(RuntimeError):
    """A git command failed (no commit yet, a missing path or blob, not a repository)."""


def git(*args: str) -> bytes:
    """Run a git command and return its output, or raise GitError with git's own message."""
    result = subprocess.run(["git", *args], capture_output=True, check=False)
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise GitError(f"git {' '.join(args)} failed: {detail or result.returncode}")
    return result.stdout


def is_env_file(path: str) -> bool:
    """True for .env and .env.* files, except the names-only .env.example."""
    name = path.rsplit("/", 1)[-1]
    return (name == ".env" or name.startswith(".env.")) and name != ".env.example"


def find_secrets(text: str) -> list[str]:
    """Return the secret patterns that match `text` (empty if it looks clean)."""
    return [p.pattern for p in SECRET_PATTERNS if p.search(text)]


def is_scanned(path: str) -> bool:
    """True for text files whose content is scanned for secrets (data folders are skipped)."""
    if path.startswith(DATA_DIRS):
        return False
    return path.endswith(SCANNED_SUFFIXES) or path.rsplit("/", 1)[-1] in SCANNED_NAMES


def committed_files() -> dict[str, int]:
    """Path -> size in bytes of every file in HEAD (one source for names, sizes and content)."""
    out: dict[str, int] = {}
    for line in git("ls-tree", "-r", "-l", "HEAD").decode("utf-8", errors="replace").splitlines():
        meta, path = line.split("\t", 1)
        size = meta.split()[3]
        out[path] = int(size) if size.isdigit() else 0
    return out


def check_sums() -> list[str]:
    """Compare every official CSV in HEAD with data/raw/SHA256SUMS."""
    failures: list[str] = []
    try:
        text = git("show", "HEAD:data/raw/SHA256SUMS").decode("utf-8", errors="replace")
    except GitError as exc:
        return [f"cannot read data/raw/SHA256SUMS: {exc}"]
    for number, line in enumerate(text.replace("\r", "").splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            failures.append(f"data/raw/SHA256SUMS line {number} is malformed: {line!r}")
            continue
        expected, name = parts[0], parts[1].strip().lstrip("*")  # '*' marks binary mode
        try:
            actual = hashlib.sha256(git("show", f"HEAD:data/raw/{name}")).hexdigest()
        except GitError as exc:
            failures.append(f"cannot read data/raw/{name} from HEAD: {exc}")
            continue
        if actual != expected:
            failures.append(f"data/raw/{name} differs from SHA256SUMS")
    return failures


def main(argv: list[str] | None = None) -> int:
    """Run every check and print one FAIL line per problem. Returns 1 if any check failed."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--tests", action="store_true", help="also run pytest")
    args = parser.parse_args(argv)
    failures: list[str] = []

    try:
        files = committed_files()
    except GitError as exc:
        print(f"FAIL  {exc}")
        print("1 check(s) failed")
        return 1

    env = [f for f in files if is_env_file(f)]
    if env:
        failures.append(f"committed env files: {env}")

    big = [
        f"{path} ({size / 1e6:.1f} MB)"
        for path, size in files.items()
        if size > MAX_BYTES and not path.startswith(DATA_DIRS)
    ]
    if big:
        failures.append(f"files over 5 MB outside data/raw/ and data/enhanced/: {big}")

    for path, size in files.items():
        if not is_scanned(path) or path in SELF_FILES or size > MAX_BYTES:
            continue
        try:
            text = git("show", f"HEAD:{path}").decode("utf-8", errors="replace")
        except GitError as exc:
            failures.append(f"cannot read {path} from HEAD: {exc}")
            continue
        hits = find_secrets(text)
        if hits:
            failures.append(f"possible secret in {path}: {hits}")

    failures += check_sums()

    if args.tests:
        result = subprocess.run([sys.executable, "-m", "pytest", "-q"], check=False)
        if result.returncode:
            failures.append("pytest failed")

    for f in failures:
        print(f"FAIL  {f}")
    print("all submission checks passed" if not failures else f"{len(failures)} check(s) failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
