"""hr_availability.hr_id must be VARCHAR for ERP UUID inserts."""
from pathlib import Path


def test_fix_hr_availability_hr_id_migration_exists_and_is_idempotent_sql():
    path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "fix_hr_availability_hr_id.sql"
    )
    assert path.is_file()
    sql = path.read_text(encoding="utf-8")
    assert "hr_availability" in sql
    assert "VARCHAR(36)" in sql
    assert "USING hr_id::text" in sql
    # Idempotent guard
    assert "typname" in sql
    assert "varchar" in sql.lower()


def test_startup_registers_hr_id_migration_path():
    main_path = Path(__file__).resolve().parents[1] / "main.py"
    text = main_path.read_text(encoding="utf-8")
    assert "fix_hr_availability_hr_id.sql" in text
