from concurrent.futures import ThreadPoolExecutor
import hashlib
from urllib.parse import urlsplit

import pytest
from pydantic import SecretStr

from app.integrations.douyin_signer import pure_algorithm
from app.integrations.douyin_signer.exceptions import DouyinSignerResponseError
from app.integrations.douyin_signer.pure_client import PureDouyinSigner
from app.integrations.douyin_signer.schemas import DouyinSignRequest


def sign_request(*, method="POST", body='{"title":"不锈钢勺子"}', query="appid=1&key=%E5%95%86%E5%93%81"):
    return DouyinSignRequest(host="fxg.jinritemai.com", full_url=f"https://fxg.jinritemai.com/product/tproduct/getSchema?{query}",
                             method=method, user_agent="synthetic-agent", body=SecretStr(body) if body else None,
                             ms_token=SecretStr("synthetic-ms-token"), aid=4272, page_id=6241)


@pytest.mark.parametrize("method,body", [("GET", ""), ("POST", '{"title":"不锈钢勺子"}')])
def test_pure_adapter_signs_the_exact_encoded_query_and_wire_body(monkeypatch, method, body):
    captured = []
    original = pure_algorithm.generate

    def observe(query, user_agent, **kwargs):
        captured.append((query, user_agent, kwargs))
        return original(query, user_agent, **kwargs)

    monkeypatch.setattr(pure_algorithm, "generate", observe)
    request = sign_request(method=method, body=body)
    result = PureDouyinSigner().sign(request)
    assert result.ok and result.a_bogus.get_secret_value()
    assert result.ms_token.get_secret_value() == "synthetic-ms-token"
    assert captured == [(urlsplit(request.full_url).query, "synthetic-agent",
                         {"body": body.encode("utf-8"), "aid": 4272, "page_id": 6241})]


def test_algorithm_hashes_utf8_post_body_and_empty_get_body():
    def double_sm3(data):
        return hashlib.new("sm3", hashlib.new("sm3", data).digest()).digest()

    options = {"aid": 4272, "page_id": 6241, "now_ms": 1793520000000,
               "enter_ms": 1793520000000, "rng": lambda: 0.2, "trace": True}
    body = '{"title":"不锈钢勺子"}'.encode("utf-8")
    post = pure_algorithm.generate("appid=1", "synthetic-agent", body=body, **options)
    get = pure_algorithm.generate("appid=1", "synthetic-agent", **options)
    assert bytes(post["body_hash"]) == double_sm3(body + b"dhzx")
    assert bytes(get["body_hash"]) == double_sm3(b"dhzx")
    assert post["result"] != get["result"]


def test_invalid_context_fails_without_echoing_sensitive_input():
    request = sign_request().model_copy(update={"full_url": "https://other.invalid/?secret=synthetic-secret"})
    with pytest.raises(DouyinSignerResponseError) as failure:
        PureDouyinSigner().sign(request)
    assert "synthetic-secret" not in str(failure.value)


def test_pure_signer_accepts_75_parallel_independent_requests():
    signer = PureDouyinSigner()

    def run(index):
        request = sign_request(query=f"appid=1&index={index}", body=f'{{"index":{index}}}')
        return signer.sign(request)

    with ThreadPoolExecutor(max_workers=75) as pool:
        results = list(pool.map(run, range(75)))
    assert len(results) == 75
    assert all(result.ok and result.a_bogus.get_secret_value() for result in results)
