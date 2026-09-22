from enum import StrEnum


class SecretProvider(StrEnum):
    ENV = "env"
    AWS_SECRETS_MANAGER = "aws-secrets-manager"


class SecretStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
