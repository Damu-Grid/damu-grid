"""Pre-submission checks (DG-39). Run from the repository root before making the repo public:

    uv run python scripts/check_submission.py          # repository checks
    uv run python scripts/check_submission.py --tests  # also run pytest

Checks what is committed (HEAD), so Windows line-ending conversion in the working copy does not
cause false alarms: no .env file, no secret-looking strings, no file over 5 MB outside data/raw/,
and every official CSV identical to data/raw/SHA256SUMS. Exits 1 if anything fails.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys

MAX_BYTES = 5 * 1024 * 1024
# The checker and its tests contain fake secret shapes on purpose.
SELF_FILES = {"scripts/check_submission.py", "tests/test_check_submission.py"}
SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),                              # AWS access key id
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),                       # common LLM API key shape
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),                  # GitHub token
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"\s]{12,}['\"]"),
]


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], check=True, capture_output=True).stdout


def is_env_file(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return (name == ".env" or name.startswith(".env.")) and name != ".env.example"


def find_secrets(text: str) -> list[str]:
    return [p.pattern for p in SECRET_PATTERNS if p.search(text)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tests", action="store_true", help="also run pytest")
    args = parser.parse_args(argv)
    failures: list[str] = []
    files = git("ls-files").decode().splitlines()

    env = [f for f in files if is_env_file(f)]
    if env:
        failures.append(f"committed env files: {env}")

    sizes = {}
    for line in git("ls-tree", "-r", "-l", "HEAD").decode().splitlines():
        meta, path = line.split("\t", 1)
        size = meta.split()[3]
        if size.isdigit():
            sizes[path] = int(size)
    big = [f"{p} ({s / 1e6:.1f} MB)" for p, s in sizes.items()
           if s > MAX_BYTES and not p.startswith("data/raw/")]
    if big:
        failures.append(f"files over 5 MB outside data/raw/: {big}")

    for path in files:
        if path.startswith("data/raw/") or not path.endswith((".py", ".md", ".toml", ".json", ".yml", ".yaml",
                                                               ".ts", ".tsx", ".js", ".txt", ".example")):
            continue
        hits = find_secrets(git("show", f"HEAD:{path}").decode("utf-8", errors="replace"))
        if hits and path not in SELF_FILES:
            failures.append(f"possible secret in {path}: {hits}")

    sums = git("show", "HEAD:data/raw/SHA256SUMS").decode().replace("\r", "").splitlines()
    for line in filter(None, sums):
        expected, name = line.split(maxsplit=1)
        actual = hashlib.sha256(git("show", f"HEAD:data/raw/{name.strip()}")).hexdigest()
        if actual != expected:
            failures.append(f"data/raw/{name} differs from SHA256SUMS")

    if args.tests:
        result = subprocess.run([sys.executable, "-m", "pytest", "-q"])
        if result.returncode:
            failures.append("pytest failed")

    for f in failures:
        print(f"FAIL  {f}")
    print("all submission checks passed" if not failures else f"{len(failures)} check(s) failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
