"""DG-39: the pre-submission checker recognises env files and secret-looking strings."""

from __future__ import annotations

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "check_submission", Path(__file__).resolve().parent.parent / "scripts" / "check_submission.py")
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def test_env_files_are_caught_but_the_example_is_allowed():
    assert check.is_env_file(".env")
    assert check.is_env_file("backend/.env.local")
    assert not check.is_env_file(".env.example")
    assert not check.is_env_file("docs/environment.md")


def test_secret_shapes_are_caught():
    assert check.find_secrets('API_KEY = "abcd1234efgh5678ijkl"')
    assert check.find_secrets("token: 'ghp_" + "a" * 36 + "'")
    assert check.find_secrets("-----BEGIN PRIVATE KEY-----")


def test_ordinary_text_is_not_a_secret():
    assert not check.find_secrets("password reset is out of scope; see .env.example for names only")
    assert not check.find_secrets('reason = "no documented recipient gap"')
