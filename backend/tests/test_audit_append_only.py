import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


def test_audit_logs_reject_update_and_delete(db_session):
    row = db_session.execute(text("SELECT id FROM audit_logs LIMIT 1")).fetchone()
    assert row is not None
    audit_id = row[0]

    with pytest.raises(DBAPIError) as update_exc:
        db_session.execute(text("UPDATE audit_logs SET action = 'mutated' WHERE id = :id"), {"id": audit_id})
        db_session.commit()
    db_session.rollback()
    assert "append-only" in str(update_exc.value).lower()

    with pytest.raises(DBAPIError) as delete_exc:
        db_session.execute(text("DELETE FROM audit_logs WHERE id = :id"), {"id": audit_id})
        db_session.commit()
    db_session.rollback()
    assert "append-only" in str(delete_exc.value).lower()
