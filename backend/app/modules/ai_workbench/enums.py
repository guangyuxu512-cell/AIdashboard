from enum import StrEnum


class GenerationMode(StrEnum):
    NORMAL_GENERATION = "NORMAL_GENERATION"
    STYLE_REPLICATION = "STYLE_REPLICATION"


class GenerationWorkMode(StrEnum):
    INSTANT = "INSTANT"
    BATCH = "BATCH"


class GenerationJobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL_FAILED = "PARTIAL_FAILED"
    FAILED = "FAILED"


class GenerationItemStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class GenerationInputRole(StrEnum):
    PRODUCT_SOURCE = "PRODUCT_SOURCE"
    STYLE_REFERENCE = "STYLE_REFERENCE"


class BatchProductScope(StrEnum):
    ALL_ENABLED = "ALL_ENABLED"
    SELECTED = "SELECTED"


class BatchTemplateSource(StrEnum):
    PRODUCT_CONFIGURED = "PRODUCT_CONFIGURED"
    CURRENT_SELECTION = "CURRENT_SELECTION"


class GenerationOutputRange(StrEnum):
    ALL = "ALL"
    MAIN_IMAGE = "MAIN_IMAGE"
    DETAIL_IMAGE = "DETAIL_IMAGE"


class OutputRole(StrEnum):
    MAIN_IMAGE = "MAIN_IMAGE"
    DETAIL_IMAGE = "DETAIL_IMAGE"


class OutputFormat(StrEnum):
    SINGLE = "SINGLE"
    COLLAGE_2X2 = "COLLAGE_2X2"


class GenerationSize(StrEnum):
    SQUARE = "1:1"
    PORTRAIT = "3:4"
    LANDSCAPE = "4:3"
    WIDESCREEN = "16:9"


class MaterialRole(StrEnum):
    PRODUCT_SOURCE = "PRODUCT_SOURCE"
    STYLE_REFERENCE = "STYLE_REFERENCE"
    AI_OUTPUT = "AI_OUTPUT"
