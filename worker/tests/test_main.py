from app.main import main
from pytest import CaptureFixture


def test_main_reports_startup(capsys: CaptureFixture[str]) -> None:
    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "started successfully" in captured.out
