from hashlib import sha256
from subprocess import CompletedProcess

from app.platforms.pdd.signer import ANTI_CONTENT_PATH, PddAntiContentSigner


PDD_ANTI_CONTENT_SHA256 = (
    "5a233da89628c7262c21877ad84b26881e422166edd3bab8ace22e5e030a487e"
)


def test_pdd_vendor_algorithm_bytes_match_the_verified_source() -> None:
    assert sha256(ANTI_CONTENT_PATH.read_bytes()).hexdigest() == PDD_ANTI_CONTENT_SHA256


def test_pdd_signer_starts_one_isolated_node_child_per_request(
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    calls: list[list[str]] = []

    def run(command, **_kwargs):  # type: ignore[no-untyped-def]
        calls.append(command)
        return CompletedProcess(command, 0, stdout="\nsynthetic-anti-content\n", stderr="")

    monkeypatch.setattr("app.platforms.pdd.signer.subprocess.run", run)
    signer = PddAntiContentSigner(node_path="node-for-test")

    assert signer.generate().get_secret_value() == "synthetic-anti-content"
    assert signer.generate().get_secret_value() == "synthetic-anti-content"
    assert len(calls) == 2
    assert all(call[:2] == ["node-for-test", "-e"] for call in calls)
