from app.schemas.v1.admins import ErpUserSyncItem, ErpUserSyncRequest, ErpUserSyncResult
from app.db.v1.enums import AdminRoles


def test_erp_sync_schemas():
    item = ErpUserSyncItem(
        erp_user_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        username="ivanov@example.com",
        full_name="Иванов Иван",
        role=AdminRoles.manager.value,
    )
    req = ErpUserSyncRequest(users=[item])
    assert len(req.users) == 1
    assert req.users[0].role == "manager"
    hr_item = ErpUserSyncItem(
        erp_user_id="b1b2c3d4-e5f6-7890-abcd-ef1234567890",
        username="hr@example.com",
        full_name="HR User",
        role="hr",
    )
    assert hr_item.role == "hr"
    result = ErpUserSyncResult(created=1, skipped=2, errors=[])
    assert result.created == 1
