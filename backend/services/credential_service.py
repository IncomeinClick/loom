"""Credential encryption service using Fernet symmetric encryption."""
from cryptography.fernet import Fernet

from backend.config import settings


class CredentialService:
    def __init__(self):
        self._fernet = None
        if settings.FERNET_KEY:
            self._fernet = Fernet(settings.FERNET_KEY.encode())

    def encrypt(self, value: str) -> str:
        if not self._fernet:
            return value  # Dev mode: no encryption
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, encrypted_value: str) -> str:
        if not self._fernet:
            return encrypted_value
        return self._fernet.decrypt(encrypted_value.encode()).decode()

    @staticmethod
    def mask(value: str) -> str:
        if len(value) <= 4:
            return "****"
        return "****" + value[-4:]

    @staticmethod
    def last_four(value: str) -> str:
        if len(value) <= 4:
            return value
        return value[-4:]


credential_service = CredentialService()
