"""Collector V2 resource signatures are not service authentication credentials."""

from copy import deepcopy
import json

import pytest

from app.modules.product_collection.contracts import canonical_sha256
from app.modules.product_collection.payload import parse_complete_package, sanitize_image_url


VIDEO = "chunks.*.promotion_v3.header_v2.cells.*.multi_preview.cells.*.cell.media.video.play_opt_model"
COMMENTS = "chunks.*.promotion_v3.components.*.slices.*.data.comments.*"
GALLERY = "chunks.*.promotion_v3.gallery.pendants.lynx_pendant_container.top_left.*.mega_data.trust_data.bubble_list.*"
PLAY_URL = "https://api-play.amemv.com/aweme/v1/play/?video_id=synthetic&file_id=synthetic&line=0&is_play_url=1&sign=synthetic-resource"
IMAGE_URL = "https://p3-product-comment-sign.byteimg.com/tos-cn-i-8y5sebgt5i/synthetic.webp?lk3s=synthetic&x-expires=1&x-signature=synthetic-resource"
ITEM_IMAGE = "chunks.*.promotion_v3.components.*.slices.*.data.item_list.*.image.url"
GATE2_COVER_URL = "https://p3-sign.douyinpic.com/tos-cn-v-800a60/synthetic.webp?dy_q=1&l=1&x-expires=1&x-signature=synthetic-resource"
GATE2_ECOM_URL = "https://p9-ecom-commentpic-sign.byteimg.com/douyin-user-image-file/synthetic.webp?lk3s=synthetic&x-expires=1&x-signature=synthetic-resource"
GATE2_P3_ECOM_URL = GATE2_ECOM_URL.replace("p9-ecom-commentpic-", "p3-ecom-commentpic-")


def _nested(path, value):
    for key in reversed(path.split(".")):
        value = [value] if key == "*" else {key: value}
    return value


def _body(path, url):
    return {
        "schemaVersion": 2, "source": "douyin", "eventType": "complete",
        "trigger": "cart_sku", "productId": "3797024140330926544",
        "capturedAt": 1792470001000, "detailCapturedAt": 1792470000000,
        "skuCapturedAt": 1792470001000, "appVersion": "0.4.10",
        "detailSha256": "a" * 64, "skuSha256": "b" * 64, "sha256": "c" * 64,
        "detailBody": _nested(path, url), "skuBody": {},
        "taskContext": {
            "jobId": "synthetic-job", "captureBatchId": "synthetic-batch",
            "jobType": "product", "sourcePlatform": "douyin",
            "sourceProductId": "3797024140330926544", "recaptureRequested": False,
        },
    }


@pytest.mark.parametrize("path,url", [
    (f"{VIDEO}.{address}.url_list.*", PLAY_URL.replace("api-play.amemv.com", host))
    for address in ("play_addr", "play_addr_lowbr", "play_addr_h264", "bit_rate.*.play_addr")
    for host in ("api-play.amemv.com", "api.amemv.com", "api-play-hl.amemv.com", "api-hl.amemv.com")
] + [
    (f"{VIDEO}.cover.url_list.*", "https://p3-sign.douyinpic.com/tos-cn-v-2e5523/synthetic.webp?dy_q=1&l=1&x-expires=1&x-signature=synthetic-resource"),
    (f"{COMMENTS}.comment_user_avatar.src", IMAGE_URL.replace("tos-cn-i-8y5sebgt5i", "aweme-avatar")),
    (f"{COMMENTS}.comment_medias_arr.*.media_image_src", IMAGE_URL),
    (f"{COMMENTS}.comment_medias_arr.*.media_click_action.actions.*.fields.image_url_array.*", IMAGE_URL.replace("p3-", "p9-")),
    (f"{GALLERY}.avatar.url_list.*", "https://p3-sellpoint1-sign.byteimg.com/synthetic.webp?rk3s=1&x-conf-key=synthetic&x-expires=1&x-signature=synthetic-resource"),
    (f"{GALLERY}.content_list.*.icon.*.url_list.*", "https://p3-sellpoint1-sign.byteimg.com/synthetic.webp?rk3s=1&x-conf-key=synthetic&x-expires=1&x-signature=synthetic-resource"),
    (f"{GALLERY}.avatar.url_list.*", "https://p11-sellpoint1-sign.byteimg.com/synthetic.webp?rk3s=1&x-conf-key=synthetic&x-expires=1&x-signature=synthetic-resource"),
    (f"{GALLERY}.content_list.*.icon.*.url_list.*", "https://p11-sellpoint1-sign.byteimg.com/synthetic.webp?rk3s=1&x-conf-key=synthetic&x-expires=1&x-signature=synthetic-resource"),
])
def test_v2_preserves_only_evidenced_signed_media_in_original_fields(path, url):
    original = _body(path, url)
    before = canonical_sha256(original)
    parsed = parse_complete_package(json.dumps(original).encode())
    assert parsed.model_dump(mode="json", by_alias=True) == original
    assert canonical_sha256(parsed.model_dump(mode="json", by_alias=True)) == before
    assert sanitize_image_url(url, allowed_hosts=frozenset({url.split("/")[2]})) == url.split("?")[0]


@pytest.mark.parametrize("url", [
    IMAGE_URL + "&access_token=synthetic-auth",
    IMAGE_URL + "&a_bogus=synthetic-request-signature",
    IMAGE_URL + "&Authorization=synthetic-auth",
    IMAGE_URL + "&cookie=synthetic-auth",
    IMAGE_URL + "&device_token=synthetic-auth",
    IMAGE_URL + "&signature=synthetic-request-signature",
    IMAGE_URL + "&auth_key=synthetic-auth",
    IMAGE_URL.replace("https:", "http:"),
    IMAGE_URL.replace("https:", "ftp:"),
    IMAGE_URL.replace("https://", "https://user:synthetic@"),
    IMAGE_URL.replace("p3-product-comment-sign.byteimg.com", "unreviewed.example.test"),
    IMAGE_URL.replace("byteimg.com/", "byteimg.com.evil.test/"),
    IMAGE_URL.replace("byteimg.com/", "byteimg.com:8443/"),
    IMAGE_URL.replace("/tos-cn-i-8y5sebgt5i/", "/api/account/"),
    IMAGE_URL.replace("x-signature", "sign"),
    IMAGE_URL + "&unexpected=synthetic",
    IMAGE_URL + "#synthetic-fragment",
    IMAGE_URL + "&width=" + "0" * 4096,
])
def test_media_exception_does_not_allow_authentication_or_other_url_context(url):
    with pytest.raises(ValueError):
        parse_complete_package(json.dumps(_body(f"{COMMENTS}.comment_medias_arr.*.media_image_src", url)).encode())


def test_resource_host_is_not_an_exception_for_requests_other_fields_sku_or_legacy():
    path = f"{VIDEO}.play_addr.url_list.*"
    for invalid in (
        _body("image", PLAY_URL),
        _body(path, PLAY_URL.replace("/aweme/v1/play/", "/passport/auth/")),
    ):
        with pytest.raises(ValueError, match="credential"):
            parse_complete_package(json.dumps(invalid).encode())
    legacy = _body(path, PLAY_URL)
    for key in ("schemaVersion", "source", "trigger", "productId", "detailCapturedAt", "appVersion", "detailSha256", "skuSha256", "sha256"):
        legacy.pop(key)
    with pytest.raises(ValueError, match="credential"):
        parse_complete_package(json.dumps(legacy).encode())
    sku = _body(path, PLAY_URL)
    sku["skuBody"], sku["detailBody"] = sku["detailBody"], {}
    with pytest.raises(ValueError, match="credential"):
        parse_complete_package(json.dumps(sku).encode())
    dotted_key = _body(path, PLAY_URL)
    dotted_key["detailBody"] = {path: PLAY_URL}
    with pytest.raises(ValueError, match="credential"):
        parse_complete_package(json.dumps(dotted_key).encode())
    fake_array = _body(path, PLAY_URL)
    fake_array["detailBody"]["chunks"] = {"*": fake_array["detailBody"]["chunks"][0]}
    with pytest.raises(ValueError, match="credential"):
        parse_complete_package(json.dumps(fake_array).encode())


@pytest.mark.parametrize("key", ["Cookie", "Authorization", "headers", "request_url", "access_token", "signature"])
def test_nested_credential_fields_stay_forbidden_beside_allowed_media(key):
    body = _body(f"{VIDEO}.play_addr.url_list.*", PLAY_URL)
    with_credentials = deepcopy(body)
    with_credentials["detailBody"]["unrelated"] = {key: "synthetic-forbidden"}
    with pytest.raises(ValueError, match="credential"):
        parse_complete_package(json.dumps(with_credentials).encode())


@pytest.mark.parametrize("path,url", [
    (f"{VIDEO}.play_addr.url_list.*", PLAY_URL.replace("api-play.amemv.com", "api-unreviewed.amemv.com")),
    ("request", PLAY_URL.replace("api-play.amemv.com", "api-hl.amemv.com")),
    (f"{VIDEO}.play_addr.url_list.*", PLAY_URL.replace("api-play.amemv.com", "api-play-hl.amemv.com").replace("/aweme/v1/play/", "/passport/auth/")),
    (f"{VIDEO}.play_addr.url_list.*", PLAY_URL.replace("api-play.amemv.com", "api-hl.amemv.com") + "&access_token=synthetic-auth"),
    (f"{GALLERY}.avatar.url_list.*", "https://p12-sellpoint1-sign.byteimg.com/synthetic.webp?x-signature=synthetic-resource"),
    (f"{GALLERY}.avatar.url_list.*", "https://p11-sellpoint1-sign.byteimg.com/synthetic.webp?x-signature=synthetic-resource&device_token=synthetic-auth"),
])
def test_cdn_variants_do_not_open_other_hosts_api_paths_fields_or_credentials(path, url):
    with pytest.raises(ValueError, match="credential"):
        parse_complete_package(json.dumps(_body(path, url)).encode())


@pytest.fixture
def gate2_complete_package():
    """Reduced real field layout; all resource IDs/signatures/hashes are synthetic."""
    body = _body(f"{VIDEO}.cover.url_list.*", GATE2_COVER_URL)
    promotion = body["detailBody"]["chunks"][0]["promotion_v3"]
    images = [IMAGE_URL, IMAGE_URL.replace("p3-", "p9-"), GATE2_ECOM_URL,
              IMAGE_URL.replace("synthetic.webp", "synthetic-second.webp")]
    promotion["components"] = [{"slices": [{"data": {
        "item_list": [{"image": {"url": url}} for url in images],
    }}]}]
    body["appVersion"] = "0.4.12"
    return body


def test_gate2_reduced_complete_package_preserves_all_five_media_and_source_hashes(
    gate2_complete_package,
):
    original = gate2_complete_package
    parsed = parse_complete_package(json.dumps(original).encode())
    normalized = parsed.model_dump(mode="json", by_alias=True)
    assert normalized == original
    assert canonical_sha256(normalized) == canonical_sha256(original)
    promotion = normalized["detailBody"]["chunks"][0]["promotion_v3"]
    assert len(promotion["components"][0]["slices"][0]["data"]["item_list"]) == 4


@pytest.mark.parametrize("path,url", [
    (f"{VIDEO}.cover.url_list.*", GATE2_COVER_URL),
    (ITEM_IMAGE, IMAGE_URL),
    (ITEM_IMAGE, IMAGE_URL.replace("p3-", "p9-")),
    (ITEM_IMAGE, GATE2_ECOM_URL),
    (ITEM_IMAGE, GATE2_P3_ECOM_URL),
])
def test_gate2_evidenced_media_fields_accept_only_resource_context(path, url):
    original = _body(path, url)
    parsed = parse_complete_package(json.dumps(original).encode())
    assert parsed.model_dump(mode="json", by_alias=True) == original
    assert sanitize_image_url(url, allowed_hosts=frozenset({url.split("/")[2]})) == url.split("?")[0]


@pytest.mark.parametrize("path,url", [
    (f"{VIDEO}.cover.url_list.*", GATE2_COVER_URL.replace("800a60", "unreviewed")),
    (f"{VIDEO}.cover.url_list.*", GATE2_COVER_URL.replace("p3-sign.", "p9-sign.")),
    (f"{VIDEO}.cover.url_list.*", GATE2_COVER_URL.replace("dy_q=1&", "")),
    (ITEM_IMAGE, IMAGE_URL.replace("/tos-cn-i-8y5sebgt5i/", "/douyin-user-image-file/")),
    (ITEM_IMAGE, GATE2_ECOM_URL.replace("/douyin-user-image-file/", "/tos-cn-i-8y5sebgt5i/")),
    (ITEM_IMAGE, GATE2_ECOM_URL.replace("p9-ecom-commentpic-", "p6-ecom-commentpic-")),
    (ITEM_IMAGE, GATE2_ECOM_URL.replace("/douyin-user-image-file/", "/api/account/")),
    (ITEM_IMAGE, GATE2_ECOM_URL.replace("https:", "http:")),
    (ITEM_IMAGE, GATE2_ECOM_URL.replace("https://", "https://user:synthetic@")),
    (ITEM_IMAGE, GATE2_ECOM_URL + "&access_token=synthetic-auth"),
    (ITEM_IMAGE, GATE2_ECOM_URL + "&unexpected=synthetic"),
    (ITEM_IMAGE, GATE2_ECOM_URL + "&x-signature=synthetic-duplicate"),
    (ITEM_IMAGE, GATE2_ECOM_URL + "&%78-signature=synthetic-encoded-duplicate"),
    (ITEM_IMAGE, GATE2_ECOM_URL.replace("lk3s=synthetic&", "")),
    (ITEM_IMAGE, GATE2_ECOM_URL + "#synthetic-fragment"),
    (f"{COMMENTS}.comment_medias_arr.*.media_image_src", GATE2_ECOM_URL),
    (f"{COMMENTS}.comment_medias_arr.*.media_image_src", GATE2_P3_ECOM_URL),
    (ITEM_IMAGE, GATE2_P3_ECOM_URL.replace("/douyin-user-image-file/", "/tos-cn-i-8y5sebgt5i/")),
    (ITEM_IMAGE, GATE2_P3_ECOM_URL.replace("https:", "http:")),
    (ITEM_IMAGE, GATE2_P3_ECOM_URL.replace("https://", "https://user:synthetic@")),
    (ITEM_IMAGE, GATE2_P3_ECOM_URL.replace("byteimg.com/", "byteimg.com:8443/")),
    (ITEM_IMAGE, GATE2_P3_ECOM_URL + "&access_token=synthetic-auth"),
    (ITEM_IMAGE, GATE2_P3_ECOM_URL + "&unexpected=synthetic"),
    (ITEM_IMAGE, GATE2_P3_ECOM_URL + "&x-signature=synthetic-duplicate"),
    (ITEM_IMAGE, GATE2_P3_ECOM_URL + "&%78-signature=synthetic-encoded-duplicate"),
    (ITEM_IMAGE, GATE2_P3_ECOM_URL.replace("lk3s=synthetic&", "")),
    (ITEM_IMAGE, GATE2_P3_ECOM_URL.replace("x-signature=synthetic-resource", "x-signature=")),
    (ITEM_IMAGE, GATE2_P3_ECOM_URL + "#synthetic-fragment"),
])
def test_gate2_media_does_not_expand_hosts_paths_queries_or_existing_comment_fields(path, url):
    with pytest.raises(ValueError, match=(
        "credential-bearing URL|URL scheme or host is not allowed|URL userinfo is forbidden"
    )):
        parse_complete_package(json.dumps(_body(path, url)).encode())


@pytest.mark.parametrize("ecom_url", [GATE2_ECOM_URL, GATE2_P3_ECOM_URL])
def test_gate2_media_remains_forbidden_in_requests_sku_legacy_and_fake_field_paths(ecom_url):
    body = _body(ITEM_IMAGE, ecom_url)
    legacy = deepcopy(body)
    for key in ("schemaVersion", "source", "trigger", "productId", "detailCapturedAt", "appVersion",
                "detailSha256", "skuSha256", "sha256"):
        legacy.pop(key)
    sku = deepcopy(body)
    sku["skuBody"], sku["detailBody"] = sku["detailBody"], {}
    dotted = deepcopy(body)
    dotted["detailBody"] = {ITEM_IMAGE: ecom_url}
    fake_array = deepcopy(body)
    fake_array["detailBody"]["chunks"] = {"*": fake_array["detailBody"]["chunks"][0]}
    for invalid in (legacy, sku, dotted, fake_array, _body("request_url", ecom_url)):
        with pytest.raises(ValueError, match="credential"):
            parse_complete_package(json.dumps(invalid).encode())


def test_gate2_media_exception_does_not_allow_plaintext_or_nested_identity(gate2_complete_package):
    for key in ("Cookie", "Authorization", "headers", "access_token"):
        invalid = deepcopy(gate2_complete_package)
        invalid["detailBody"]["nested"] = {"identity": {key: "synthetic-forbidden"}}
        with pytest.raises(ValueError, match="credential"):
            parse_complete_package(json.dumps(invalid).encode())


def test_p3_ecom_reduced_package_preserves_raw_and_keeps_identity_forbidden(gate2_complete_package):
    body = gate2_complete_package
    items = body["detailBody"]["chunks"][0]["promotion_v3"]["components"][0]["slices"][0]["data"]["item_list"]
    items[2]["image"]["url"] = GATE2_P3_ECOM_URL
    parsed = parse_complete_package(json.dumps(body).encode())
    assert parsed.model_dump(mode="json", by_alias=True) == body
    assert canonical_sha256(parsed.model_dump(mode="json", by_alias=True)) == canonical_sha256(body)
    for key in ("Cookie", "Authorization", "headers", "access_token"):
        invalid = deepcopy(body)
        invalid["detailBody"]["nested"] = {"identity": {key: "synthetic-forbidden"}}
        with pytest.raises(ValueError, match="credential"):
            parse_complete_package(json.dumps(invalid).encode())
