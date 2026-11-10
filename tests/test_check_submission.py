"""DG-39: the pre-submission checker finds env files, secrets, big files and altered datasets."""

from __future__ import annotations

import hashlib
import importlib.util
import subprocess
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "check_submission", Path(__file__).resolve().parent.parent / "scripts" / "check_submission.py"
)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

CSV = b"a,b\n1,2\n"


def test_env_files_are_caught_but_the_example_is_allowed():
    """.env and .env.* are refused; .env.example only holds names."""
    assert check.is_env_file(".env")
    assert check.is_env_file("backend/.env.local")
    assert not check.is_env_file(".env.example")
    assert not check.is_env_file("docs/environment.md")


def test_secret_shapes_are_caught():
    """Typical key, token and private-key shapes are recognised."""
    assert check.find_secrets('API_KEY = "abcd1234efgh5678ijkl"')
    assert check.find_secrets("token: 'ghp_" + "a" * 36 + "'")
    assert check.find_secrets("-----BEGIN PRIVATE KEY-----")


def test_ordinary_text_is_not_a_secret():
    """Prose that merely mentions passwords or keys is not flagged."""
    assert not check.find_secrets("password reset is out of scope; see .env.example for names only")
    assert not check.find_secrets('reason = "no documented recipient gap"')


def test_scanned_file_types():
    """Config, shell, notebook, csv and Dockerfile are scanned; the data folders are not."""
    for path in ("a.ini", "b.cfg", "c.sh", "d.ipynb", "e.csv", "Dockerfile", "x/Dockerfile"):
        assert check.is_scanned(path), path
    for path in ("data/raw/units.csv", "data/enhanced/temperature_logs.csv", "image.png"):
        assert not check.is_scanned(path), path


def _repo(tmp_path: Path, files: dict[str, bytes], sums: str | None = None) -> None:
    """Create a git repository in tmp_path with the files, a SHA256SUMS and one commit."""
    run = lambda *a: subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)  # noqa: E731
    run("init", "-q")
    run("config", "user.name", "t")
    run("config", "user.email", "t@example.com")
    for name, data in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    if sums is None:
        sums = f"{hashlib.sha256(CSV).hexdigest()}  units.csv\n"
    (tmp_path / "data/raw").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data/raw/SHA256SUMS").write_text(sums)
    run("add", "-A")
    run("commit", "-q", "-m", "fixture")


@pytest.fixture
def run_in(tmp_path, monkeypatch, capsys):
    """Run check.main() inside tmp_path and return (exit code, printed output)."""
    monkeypatch.chdir(tmp_path)

    def go():
        """Test helper: go."""
        code = check.main([])
        return code, capsys.readouterr().out

    return go


def test_clean_repository_passes(tmp_path, run_in):
    """No env file, no secret, nothing big, dataset identical to SHA256SUMS."""
    _repo(tmp_path, {"data/raw/units.csv": CSV, "README.md": b"hello"})
    assert run_in() == (0, "all submission checks passed\n")


def test_env_file_and_big_file_are_reported(tmp_path, run_in):
    """A committed .env and a 6 MB file fail; the two data folders are exempt from the limit."""
    big = b"x" * (6 * 1024 * 1024)
    _repo(tmp_path, {"data/raw/units.csv": CSV, ".env": b"A=1", "notes/big.bin": big,
                     "data/enhanced/logs.csv": big})
    code, out = run_in()
    assert code == 1
    assert "committed env files" in out and "notes/big.bin" in out
    assert "data/enhanced/logs.csv" not in out


def test_secret_in_a_scanned_file_is_reported(tmp_path, run_in):
    """A key-shaped string in a .sh file (a newly scanned type) fails."""
    _repo(tmp_path, {"data/raw/units.csv": CSV, "run.sh": b'API_KEY="abcd1234efgh5678ijkl"\n'})
    code, out = run_in()
    assert code == 1 and "possible secret in run.sh" in out


def test_altered_dataset_is_reported(tmp_path, run_in):
    """A CSV whose hash differs from SHA256SUMS fails."""
    _repo(tmp_path, {"data/raw/units.csv": b"a,b\n9,9\n"})
    code, out = run_in()
    assert code == 1 and "data/raw/units.csv differs from SHA256SUMS" in out


def test_malformed_and_binary_mode_sums_lines(tmp_path, run_in):
    """A malformed line is a FAIL (no crash); a leading '*' (binary mode) is accepted."""
    digest = hashlib.sha256(CSV).hexdigest()
    _repo(tmp_path, {"data/raw/units.csv": CSV}, sums=f"{digest} *units.csv\nnot-a-valid-line\n")
    code, out = run_in()
    assert code == 1
    assert "line 2 is malformed" in out and "differs" not in out


def test_missing_blob_is_a_failure_not_a_traceback(tmp_path, run_in):
    """A SHA256SUMS entry for a file that is not committed fails cleanly."""
    _repo(tmp_path, {"data/raw/units.csv": CSV},
          sums=f"{hashlib.sha256(CSV).hexdigest()}  units.csv\n{'0' * 64}  ghost.csv\n")
    code, out = run_in()
    assert code == 1 and "cannot read data/raw/ghost.csv" in out


def test_repository_without_a_commit_fails_cleanly(tmp_path, monkeypatch, capsys):
    """git init without a commit gives a FAIL line and exit code 1."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    code = check.main([])
    out = capsys.readouterr().out
    assert code == 1 and out.startswith("FAIL") and "check(s) failed" in out
