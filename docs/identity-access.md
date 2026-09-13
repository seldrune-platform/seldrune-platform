# Identity and access

Seldrune Core v0.3 introduces the first authentication and authorization boundary.

## Authentication

- Passwords are hashed with the recommended `pwdlib` password hash configuration.
- Access tokens are signed JWTs with an expiry and a required token type.
- Production refuses to start with the development JWT secret.
- Authentication failures return the same response for unknown users and bad passwords.

## Registration

`POST /api/v1/auth/register` creates:

1. a user,
2. an organization,
3. an owner membership,
4. an audit event,
5. a short-lived access token.

Public registration is useful while building the platform. Before public production launch it should
be placed behind an explicit product policy such as invite-only onboarding, verified email, or an
approved organization creation flow.

## Authorization

Organization authorization remains database-backed. The JWT identifies the user; the server then
loads the current membership and evaluates the role against the RBAC permission map. Roles are not
trusted merely because they appear in a token.

Current roles:

- owner
- admin
- member
- auditor

## Production controls still required

Before accepting real customer data, add:

- email verification,
- MFA/passkeys,
- refresh-token rotation or an external identity provider,
- login rate limits,
- account recovery,
- session revocation,
- secret storage in the cloud secret manager,
- security event monitoring,
- organization invitation workflows.
