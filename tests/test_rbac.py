from backend.app.core.rbac import Permission, Role, has_permission


def test_owner_has_every_permission() -> None:
    for permission in Permission:
        assert has_permission(Role.OWNER, permission)


def test_member_can_run_agents_but_cannot_manage_members() -> None:
    assert has_permission(Role.MEMBER, Permission.AGENTS_RUN)
    assert not has_permission(Role.MEMBER, Permission.MEMBERS_MANAGE)


def test_auditor_can_read_audit_but_cannot_manage_org() -> None:
    assert has_permission(Role.AUDITOR, Permission.AUDIT_READ)
    assert not has_permission(Role.AUDITOR, Permission.ORG_MANAGE)
