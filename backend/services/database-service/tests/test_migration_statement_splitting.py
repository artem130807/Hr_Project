from pathlib import Path


def test_hiring_request_workflow_uses_one_statement_per_migration_chunk():
    service_root = Path(__file__).resolve().parents[1]
    source = (service_root / "migrations" / "hiring_request_workflow.sql").read_text(
        encoding="utf-8"
    )

    chunks = [chunk.strip() for chunk in source.split("-- migrate:split") if chunk.strip()]

    assert chunks
    assert all(chunk.count(";") == 1 for chunk in chunks)
    assert len(chunks) == 7


def test_erp_actor_id_migration_drops_legacy_foreign_keys_before_type_change():
    service_root = Path(__file__).resolve().parents[1]
    migration = service_root / "migrations" / "erp_actor_ids.sql"
    source = migration.read_text(encoding="utf-8")
    main_source = (service_root / "main.py").read_text(encoding="utf-8")

    assert "DROP CONSTRAINT" in source
    assert "ALTER COLUMN actor_id TYPE VARCHAR(36) USING actor_id::text" in source
    assert "ALTER COLUMN author_id TYPE VARCHAR(36) USING author_id::text" in source
    assert "erp_actor_ids.sql" in main_source
