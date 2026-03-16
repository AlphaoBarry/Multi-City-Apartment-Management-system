"""Tests for tenant management — database/db_service tenant functions"""

from database.db_service import register_tenant, get_tenants, update_tenant


def test_register_tenant_returns_id():
    tid = register_tenant("Alice", "Smith", "AA111111A", "alice@test.com", "07700000001")
    assert tid is not None
    assert isinstance(tid, str)
    assert len(tid) > 0


def test_duplicate_ni_number_returns_none():
    register_tenant("Alice", "Smith", "BB222222B", "alice1@test.com", "07700000001")
    result = register_tenant("Bob", "Jones", "BB222222B", "bob@test.com", "07700000002")
    assert result is None


def test_get_tenants_count():
    register_tenant("One", "Tenant", "CC333333C", "one@test.com", "07700000001")
    register_tenant("Two", "Tenant", "DD444444D", "two@test.com", "07700000002")
    tenants = get_tenants()
    assert len(tenants) == 2


def test_update_tenant_field():
    tid = register_tenant("Old", "Name", "EE555555E", "old@test.com", "07700000001")
    result = update_tenant(tid, first_name="New")
    assert result is True
    tenants = get_tenants()
    updated = [t for t in tenants if t["tenant_id"] == tid][0]
    assert updated["first_name"] == "New"
