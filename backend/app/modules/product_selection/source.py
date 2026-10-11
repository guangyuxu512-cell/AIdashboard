"""Versioned, credential-free source identity, not a date/channel mapper."""

from datetime import date, datetime
from hashlib import sha256
import json

from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator


class SelectionSourceScope(BaseModel):
    """Record actual business parameters without inferring their enum meaning.

    Pagination is deliberately not part of identity. No defaults, relative
    dates, session fields, tracking parameters or signed URLs are accepted.
    Accepting a scope for persistence does not validate it for platform I/O.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    industry_id: StrictStr = Field(min_length=1, max_length=128)
    category_id: StrictStr = Field(max_length=2048)
    brand_type: StrictStr = Field(min_length=1, max_length=32)
    price_bin: StrictStr = Field(min_length=1, max_length=200)
    search_info: StrictStr = Field(max_length=200)
    rank_data_type: StrictStr = Field(min_length=1, max_length=32)
    begin_date: StrictStr
    end_date: StrictStr
    date_type: StrictStr = Field(min_length=1, max_length=32)
    activity_id: StrictStr = Field(max_length=128)

    @model_validator(mode="after")
    def validate_dates(self) -> "SelectionSourceScope":
        start = datetime.strptime(self.begin_date, "%Y/%m/%d 00:00:00")
        end = datetime.strptime(self.end_date, "%Y/%m/%d 00:00:00")
        if (
            start.strftime("%Y/%m/%d 00:00:00") != self.begin_date
            or end.strftime("%Y/%m/%d 00:00:00") != self.end_date
            or start > end
        ):
            raise ValueError("Explicit source dates must be ordered and canonical")
        return self

    def context(self) -> dict[str, object]:
        return {
            "version": 1,
            "platform": "douyin",
            "endpoint": "product_rank/video_bring_good",
            "business": self.model_dump(),
        }

    def fingerprint(self) -> str:
        encoded = json.dumps(
            self.context(), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        return sha256(encoded).hexdigest()

    @property
    def period_begin(self) -> date:
        return datetime.strptime(self.begin_date, "%Y/%m/%d 00:00:00").date()

    @property
    def period_end(self) -> date:
        return datetime.strptime(self.end_date, "%Y/%m/%d 00:00:00").date()
