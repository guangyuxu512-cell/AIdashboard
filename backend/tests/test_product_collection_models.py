from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, UniqueConstraint

from app.modules.product_collection.models import (
    ProductCollectionCaptureAttempt,
    ProductCollectionDispatch,
    ProductCollectionItem,
    ProductCollectionPersistReceipt,
    ProductCollectionRequest,
    ProductCollectionUploadReceipt,
    ProductLibraryGroup,
    ProductLibraryProduct,
    ProductLibraryProductVersion,
)
from app.modules.product_selection.models import ProductSelectionCandidate


def _named(table, kind):
    return {item.name: item for item in table.constraints | table.indexes if isinstance(item, kind)}


def test_mobile_collection_models_register_the_approved_nine_tables():
    models = (
        ProductLibraryGroup,
        ProductLibraryProduct,
        ProductLibraryProductVersion,
        ProductCollectionRequest,
        ProductCollectionItem,
        ProductCollectionDispatch,
        ProductCollectionCaptureAttempt,
        ProductCollectionUploadReceipt,
        ProductCollectionPersistReceipt,
    )
    assert {model.__tablename__ for model in models} == {
        "product_library_groups",
        "product_library_products",
        "product_library_product_versions",
        "product_collection_requests",
        "product_collection_items",
        "product_collection_dispatches",
        "product_collection_capture_attempts",
        "product_collection_upload_receipts",
        "product_collection_persist_receipts",
    }


def test_candidate_and_team_owned_entities_have_composite_reference_targets():
    candidate_unique = _named(ProductSelectionCandidate.__table__, UniqueConstraint)
    assert tuple(candidate_unique["uq_selection_candidate_id_team"].columns.keys()) == (
        "candidate_id",
        "team_id",
    )

    item_foreign_keys = _named(ProductCollectionItem.__table__, ForeignKeyConstraint)
    assert tuple(item_foreign_keys["fk_pc_item_candidate_team"].columns.keys()) == (
        "candidate_id",
        "team_id",
    )
    assert tuple(item_foreign_keys["fk_collection_item_current_dispatch"].columns.keys()) == (
        "current_dispatch_id",
        "item_id",
        "team_id",
    )

    product_foreign_keys = _named(ProductLibraryProduct.__table__, ForeignKeyConstraint)
    assert tuple(product_foreign_keys["fk_library_product_adopted_version"].columns.keys()) == (
        "adopted_version_id",
        "product_id",
        "team_id",
    )


def test_active_dispatch_and_attempt_uniques_match_the_approved_state_sets():
    dispatch_indexes = _named(ProductCollectionDispatch.__table__, Index)
    dispatch = dispatch_indexes["uq_pc_dispatch_active_item"]
    assert dispatch.unique
    assert str(dispatch.dialect_options["postgresql"]["where"]) == (
        "state IN ('pending_delivery','delivering','dispatched','running')"
    )

    attempt_indexes = _named(ProductCollectionCaptureAttempt.__table__, Index)
    attempt = attempt_indexes["uq_pc_attempt_active_dispatch"]
    assert attempt.unique
    assert str(attempt.dialect_options["postgresql"]["where"]) == (
        "state IN ('registered','running','received','processing')"
    )


def test_finished_at_and_upload_settlement_combinations_are_database_constrained():
    for model in (
        ProductCollectionRequest,
        ProductCollectionItem,
        ProductCollectionDispatch,
        ProductCollectionCaptureAttempt,
    ):
        assert "finished_at" in model.__table__.columns
        assert any(
            constraint.name.endswith("finished_terminal")
            for constraint in model.__table__.constraints
            if isinstance(constraint, CheckConstraint)
        )

    upload_checks = _named(ProductCollectionUploadReceipt.__table__, CheckConstraint)
    assert "ck_product_collection_upload_receipts_terminal_has_settlement" in upload_checks
    assert "ck_product_collection_upload_receipts_settlement_failed_error" in upload_checks
    assert "ck_product_collection_upload_receipts_settlement_retry_state" in upload_checks
    assert "ck_product_collection_upload_receipts_settled_clean" in upload_checks

    upload_indexes = _named(ProductCollectionUploadReceipt.__table__, Index)
    assert tuple(upload_indexes["ix_pc_upload_settlement"].columns.keys()) == (
        "gateway_settlement_state",
        "next_attempt_at",
        "upload_receipt_id",
    )

    assert "gateway_settlement_state" not in ProductCollectionPersistReceipt.__table__.columns
    assert "settlement_error_code" not in ProductCollectionPersistReceipt.__table__.columns
    assert "gateway_settlement_state" in ProductCollectionUploadReceipt.__table__.columns
    assert "settlement_error_code" in ProductCollectionUploadReceipt.__table__.columns


def test_upload_persisted_relation_is_not_faked_as_a_single_row_check():
    upload_checks = [
        str(constraint.sqltext)
        for constraint in ProductCollectionUploadReceipt.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    ]
    assert all("persist_receipt" not in statement for statement in upload_checks)
    persist_foreign_keys = _named(ProductCollectionPersistReceipt.__table__, ForeignKeyConstraint)
    assert "fk_pc_persist_upload_team" in persist_foreign_keys
