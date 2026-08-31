from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CryptoVault:
    def __init__(self):
        self.key = None

    def derive_key(self, master_password: str, salt: bytes) -> bytes:
        """Derives the AES key from the master password and a per-record salt."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600_000,
        )
        self.key = kdf.derive(master_password.encode("utf-8"))
        return self.key

    def encrypt(self, key: str, nonce: bytes, secret_key: bytes | None = None) -> bytes:
        cipher = AESGCM(secret_key if secret_key is not None else self.key)
        return cipher.encrypt(nonce, key.encode("utf-8"), None)

    def decrypt(self, encoded_key: bytes, nonce: bytes, secret_key: bytes | None = None) -> str:
        cipher = AESGCM(secret_key if secret_key is not None else self.key)
        decrypted = cipher.decrypt(nonce, encoded_key, None)
        return decrypted.decode("utf-8")
