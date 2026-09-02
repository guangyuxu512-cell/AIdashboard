from app.core.exceptions import AppError


class TemplateGroupNotFoundError(AppError):
    code = "TEMPLATE_GROUP_NOT_FOUND"
    message = "模板组不存在"
    status_code = 404


class PromptTemplateNotFoundError(AppError):
    code = "PROMPT_TEMPLATE_NOT_FOUND"
    message = "提示词模板不存在"
    status_code = 404


class ProductMaterialGroupNotFoundError(AppError):
    code = "PRODUCT_MATERIAL_GROUP_NOT_FOUND"
    message = "商品素材组不存在"
    status_code = 404


class TemplateGroupInUseError(AppError):
    code = "TEMPLATE_GROUP_IN_USE"
    message = "模板组仍被商品素材组引用，无法删除"
    status_code = 409


class TemplateSequenceInvalidError(AppError):
    code = "TEMPLATE_SEQUENCE_INVALID"
    message = "模板顺序无效"
    status_code = 422


class TemplateBindingInvalidError(AppError):
    code = "TEMPLATE_BINDING_INVALID"
    message = "模板组绑定关系无效"
    status_code = 422


class MaterialAssetRoleInvalidError(AppError):
    code = "MATERIAL_ASSET_ROLE_INVALID"
    message = "素材角色不允许执行当前变更"
    status_code = 409
