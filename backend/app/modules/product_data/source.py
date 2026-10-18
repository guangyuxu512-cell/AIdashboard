"""Frozen, versioned native product-list scopes; no network or DB access."""

from datetime import date, datetime, timedelta
import hashlib
import json
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, model_validator

from app.platforms.douyin.product_data import PRODUCT_METRIC_CONTRACT


NativePeriod = Literal["1d", "7d", "30d"]
PERIODS = {"1d": (1, "20"), "7d": (7, "21"), "30d": (30, "23")}
REQUEST_CONTRACT = "compass_product_list_request74_v1"
# Exact order from the accepted single-page 74-field projection. No captured
# header, signature, fingerprint or credential is part of this contract.
REQUESTED_METRICS = tuple((
    "receive_amt,pay_amt_exclude_refund,trans_amt,pay_amt,pay_cnt,ad_costed_amt,ad_cost_ratio,"
    "qc_ad_cost,pay_refund_success_amt,product_show_ucnt,product_click_ucnt,pay_ucnt,net_trans_amt,"
    "product_show_pay_converse_uv_rate,comment_good_eval_ratio,good_eval_cnt,product_bad_eval_order_cnt,"
    "product_bad_eval_ratio,comment_bad_eval_ratio,product_quality_refund_order_cnt,product_quality_refund_ratio,"
    "ext_lgt_return_order_cnt,ext_lgt_return_ratio,complaint_order_cnt_lt14,complaint_ratio,unsatisfied_convcmnt_cnt,"
    "ad_receive_amt,ad_receive_refund_amt,ad_efficiency,click_add_to_cart_uv,product_add_show_converse_uv_ratio,"
    "product_add_pay_converse_uv_ratio,product_wish_ucnt,product_wish_show_converse_uv_ratio,"
    "product_wish_pay_converse_uv_ratio,refund_amt,refund_order_cnt,refund_ucnt,refund_combo_cnt,"
    "pay_refund_success_order_cnt,pay_refund_ratio,sale_pay_refund_ratio,sold_pay_refund_ratio,"
    "sale_pay_refund_success_amt,sale_pay_refund_success_order_cnt,sale_pay_refund_success_ucnt,"
    "sale_pay_refund_success_combo_cnt,sold_pay_refund_success_amt,sold_pay_refund_success_order_cnt,"
    "sold_pay_refund_success_ucnt,sold_pay_refund_success_combo_cnt,pay_refund_trans_amt_1h,"
    "pay_refund_order_cnt_1h,pay_refund_trans_ratio_1h,pay_combo_cnt,per_user_price,pay_cnt_exclude_refund,"
    "settle_amt,real_commission,deposit_pay_cnt,deposit_pay_amt,first_onshelf_date,pay_qc_plat_coupon_amt,"
    "pay_plat_cost_amt,pay_qc_plat_coupon_amt_without_refund,pay_plat_cost_amt_without_refund,net_pay_cnt,"
    "ship_amt,payin3d_pay_ship_amt_rate,pay_refund_receive_amt,product_click_cnt,"
    "product_show_click_converse_uv_rate,product_click_pay_converse_uv_rate,product_show_cnt"
).split(","))


class ProductDataSlice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    shop_id: UUID
    period: NativePeriod
    start_date: date
    end_date: date
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"
    platform: Literal["douyin"] = "douyin"
    sale_type: Literal["1"] = "1"
    content_type: Literal["1"] = "1"
    request_contract: Literal["compass_product_list_request74_v1"] = REQUEST_CONTRACT
    metric_contract: Literal["compass_product_list_core17_v1"] = PRODUCT_METRIC_CONTRACT

    @model_validator(mode="after")
    def native_window(self):
        if (self.end_date - self.start_date).days != PERIODS[self.period][0] - 1:
            raise ValueError("Only the exact native preset duration is supported")
        return self

    @property
    def date_type(self) -> str:
        return PERIODS[self.period][1]

    @property
    def source_scope_hash(self) -> str:
        return self._hash(self.model_dump(mode="json"))

    @property
    def rolling_series_hash(self) -> str:
        return self._hash(self.model_dump(mode="json", exclude={"start_date", "end_date"}))

    @staticmethod
    def _hash(value: dict) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def business_query(self, page_no: int) -> dict[str, str]:
        if type(page_no) is not int or page_no < 1:
            raise ValueError("Page must be a positive integer")
        return {
            "date_type": self.date_type,
            "begin_date": self.start_date.strftime("%Y/%m/%d 00:00:00"),
            "end_date": self.end_date.strftime("%Y/%m/%d 00:00:00"),
            "is_activity": "false", "activity_id": "", "key_word": "",
            "index_selected": ",".join(REQUESTED_METRICS),
            "sale_type": self.sale_type, "content_type": self.content_type,
            "cate_ids": "", "cate_ids_original": "0", "product_tab": "0",
            "only_abnormal": "false", "only_drop_gmv": "false", "only_drop_product_show": "false",
            "use_customize_gmv": "false", "use_customize_product_show": "false",
            "abnormal_threshold_gmv": "0", "abnormal_threshold_product_show": "0",
            "new_version": "true", "page_no": str(page_no), "page_size": "10",
        }


def freeze_native_slice(shop_id: UUID, period: NativePeriod, accepted_at: datetime) -> ProductDataSlice:
    if accepted_at.utcoffset() is None:
        raise ValueError("Acceptance time must include a timezone")
    yesterday = accepted_at.astimezone(ZoneInfo("Asia/Shanghai")).date() - timedelta(days=1)
    return ProductDataSlice(
        shop_id=shop_id, period=period,
        start_date=yesterday - timedelta(days=PERIODS[period][0] - 1), end_date=yesterday,
    )
