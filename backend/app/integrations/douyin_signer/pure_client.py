"""In-process signer for the existing, task-scoped Worker precheck contract."""
from time import perf_counter
from urllib.parse import urlsplit

from app.integrations.douyin_signer import pure_algorithm
from app.integrations.douyin_signer.exceptions import DouyinSignerResponseError
from app.integrations.douyin_signer.schemas import DouyinSignRequest, DouyinSignResult


class PureDouyinSigner:
    def sign(self, request: DouyinSignRequest) -> DouyinSignResult:
        started = perf_counter()
        try:
            url = urlsplit(request.full_url or "")
            if (url.scheme != "https" or url.hostname != "fxg.jinritemai.com"
                    or url.port not in (None, 443) or url.username is not None
                    or url.password is not None or url.fragment or not url.query
                    or request.method not in {"GET", "POST"} or not request.user_agent
                    or request.aid is None or request.page_id is None):
                raise ValueError("invalid precheck signing context")
            body = request.body.get_secret_value().encode("utf-8") if request.body else b""
            if request.method == "GET" and body:
                raise ValueError("unexpected GET body")
            signature = pure_algorithm.generate(url.query, request.user_agent, body=body,
                                                aid=request.aid, page_id=request.page_id)
            if not signature or not isinstance(signature, str):
                raise ValueError("invalid signature")
            return DouyinSignResult(ok=True, a_bogus=signature, msToken=request.ms_token,
                                    duration_ms=int((perf_counter() - started) * 1000),
                                    version="abogus-python-pure-1")
        except Exception:
            # Never echo the query, body, session or platform URL in an error.
            raise DouyinSignerResponseError() from None
