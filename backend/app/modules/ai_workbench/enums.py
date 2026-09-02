from enum import StrEnum


class GenerationMode(StrEnum):
    NORMAL_GENERATION = "NORMAL_GENERATION"
    STYLE_REPLICATION = "STYLE_REPLICATION"


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
