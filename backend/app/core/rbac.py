from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    AUDITOR = "auditor"


class Permission(StrEnum):
    ORG_READ = "org:read"
    ORG_MANAGE = "org:manage"
    MEMBERS_READ = "members:read"
    MEMBERS_MANAGE = "members:manage"
    AGENTS_RUN = "agents:run"
    AGENTS_MANAGE = "agents:manage"
    AUDIT_READ = "audit:read"
    BILLING_READ = "billing:read"
    BILLING_MANAGE = "billing:manage"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: frozenset(Permission),
    Role.ADMIN: frozenset(
        {
            Permission.ORG_READ,
            Permission.ORG_MANAGE,
            Permission.MEMBERS_READ,
            Permission.MEMBERS_MANAGE,
            Permission.AGENTS_RUN,
            Permission.AGENTS_MANAGE,
            Permission.AUDIT_READ,
            Permission.BILLING_READ,
        }
    ),
    Role.MEMBER: frozenset(
        {
            Permission.ORG_READ,
            Permission.MEMBERS_READ,
            Permission.AGENTS_RUN,
        }
    ),
    Role.AUDITOR: frozenset(
        {
            Permission.ORG_READ,
            Permission.MEMBERS_READ,
            Permission.AUDIT_READ,
            Permission.BILLING_READ,
        }
    ),
}


def has_permission(role: Role | str, permission: Permission | str) -> bool:
    resolved_role = Role(role)
    resolved_permission = Permission(permission)
    return resolved_permission in ROLE_PERMISSIONS[resolved_role]
