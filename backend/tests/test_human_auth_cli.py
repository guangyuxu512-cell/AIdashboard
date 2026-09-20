from __future__ import annotations

import argparse

import pytest

from app.cli.human_auth import _read_confirmed_password, build_parser


def _all_actions(parser: argparse.ArgumentParser) -> list[argparse.Action]:
    actions = list(parser._actions)
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for child in action.choices.values():
                actions.extend(_all_actions(child))
    return actions


def test_cli_has_no_raw_password_argument() -> None:
    assert all(action.dest != "password" for action in _all_actions(build_parser()))


def test_cli_exposes_explicit_super_account_designation_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["designate-super-account", "00000000-0000-4000-8000-000000000001"],
    )

    assert args.command == "designate-super-account"
    assert str(args.user_id) == "00000000-0000-4000-8000-000000000001"


def test_cli_reads_and_confirms_password_with_getpass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = iter(["safe-password-value", "safe-password-value"])
    prompts: list[str] = []

    def fake_getpass(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr("app.cli.human_auth.getpass.getpass", fake_getpass)

    assert _read_confirmed_password() == "safe-password-value"
    assert prompts == ["新密码: ", "再次输入新密码: "]


def test_cli_rejects_mismatched_password_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = iter(["safe-password-value", "different-password"])
    monkeypatch.setattr(
        "app.cli.human_auth.getpass.getpass",
        lambda _prompt: next(answers),
    )

    with pytest.raises(ValueError, match="两次输入的密码不一致"):
        _read_confirmed_password()
