import httpx
import pytest

from app.modules.product_collection.gateway import ProductCollectionGatewayError
from tests.test_product_collection_gateway import _gateway, CONTROL_TOKEN, GATEWAY_ID


def status_body(**changes):
    return {
        "ok": True, "jobId": "synthetic-status-job", "externalJobId": "pcd_v1_synthetic",
        "status": "failed", "sourcePlatform": "douyin", "sourceProductId": "3797024140330926544",
        "captureBatchId": "synthetic-status-batch-3", "attempts": 3, "maxAttempts": 3,
        "lastError": "中控确认超时：购物车已经点击，有限自动恢复后仍未生成本批次完整包。请检查 LSPosed 作用域、采集插件和抖音进程。",
        "updatedAt": "2026-10-25T04:00:00Z",
        "finishedAt": "2026-10-25T04:00:00Z", **changes,
    }


def test_status_uses_control_read_only_contract_and_safe_reason():
    def handle(request):
        assert request.method == "GET" and request.url.path == "/api/v1/jobs/synthetic-status-job/result"
        assert request.url.params["externalJobId"] == "pcd_v1_synthetic"
        assert request.content == b"" and "cookie" not in request.headers
        assert request.headers["authorization"] == f"Bearer {CONTROL_TOKEN}"
        return httpx.Response(200, json=status_body())

    result = _gateway(handle).status(gateway_job_id="synthetic-status-job", external_job_id="pcd_v1_synthetic")
    assert result.gateway_id == GATEWAY_ID and result.attempts == result.max_attempts == 3
    assert result.source_product_id == "3797024140330926544"
    assert result.error_message == "手机采集等待本批次完整包超时（尝试 3/3 次）"
    assert "LSPosed" not in result.error_message


@pytest.mark.parametrize("change", [
    {"jobId": "wrong-job"}, {"status": "unknown"}, {"attempts": "3"},
    {"sourceProductId": 3797024140330926544}, {"ok": 1},
    {"result": {"token": "synthetic-secret"}}, {"updatedAt": "2026-10-25T04:00:00"},
])
def test_status_rejects_unknown_or_malformed_contract_without_exposing_input(change):
    gateway = _gateway(lambda _: httpx.Response(200, json=status_body(**change)))
    with pytest.raises(ProductCollectionGatewayError) as error:
        gateway.status(gateway_job_id="synthetic-status-job", external_job_id="pcd_v1_synthetic")
    assert error.value.failure_code == "PRODUCT_COLLECTION_GATEWAY_RESPONSE_INVALID"
    assert "synthetic-secret" not in str(error.value)


def test_status_drops_unreviewed_free_text_instead_of_storing_secrets():
    raw = "Cookie=sessionid=synthetic-secret https://example.test/private?token=synthetic-secret"
    result = _gateway(lambda _: httpx.Response(200, json=status_body(lastError=raw))).status(
        gateway_job_id="synthetic-status-job", external_job_id="pcd_v1_synthetic",
    )
    assert result.error_message == "手机采集网关任务已失败（尝试 3/3 次）"
    assert "synthetic-secret" not in repr(result) and "https://" not in repr(result)


def test_status_network_error_is_classified_without_raw_details():
    def fail(request):
        raise httpx.ReadTimeout("synthetic-secret", request=request)

    with pytest.raises(ProductCollectionGatewayError) as error:
        _gateway(fail).status(gateway_job_id="synthetic-status-job", external_job_id="pcd_v1_synthetic")
    assert error.value.failure_code == "PRODUCT_COLLECTION_GATEWAY_TIMEOUT"
    assert "synthetic-secret" not in str(error.value)


def test_status_external_identity_is_url_encoded_without_loss():
    external = "pcd_v1_pairing&scope/encoded"

    def handle(request):
        assert request.url.params["externalJobId"] == external
        assert request.url.query == b"externalJobId=pcd_v1_pairing%26scope%2Fencoded"
        return httpx.Response(200, json=status_body(externalJobId=external))

    assert _gateway(handle).status(gateway_job_id="synthetic-status-job", external_job_id=external).external_job_id == external
