import secrets

import asyncpg
from cryptography.exceptions import InvalidTag
from apikeymanager.config import db_url
from apikeymanager.crypto import CryptoVault


class MasterPasswordDecryptionError(Exception):
    def __init__(self, record_id: int):
        self.record_id = record_id
        super().__init__(f"Could not decrypt API key record {record_id}.")


class DatabaseManager:
    def __init__(self):
        self.pool = None

    async def connect(self):
        if self.pool is None:
            self.pool = await asyncpg.create_pool(dsn=db_url)

    async def close(self):
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def setup_database(self):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_data (
                    id SERIAL PRIMARY KEY,
                    service VARCHAR(100) NOT NULL,
                    username VARCHAR(100) NOT NULL,
                    salt BYTEA NOT NULL,
                    nonce BYTEA NOT NULL,
                    api_key BYTEA NOT NULL,
                    UNIQUE (service, username)
                );
                """
            )

    async def save_credentials(
        self,
        service: str,
        username: str,
        salt: bytes,
        nonce: bytes,
        api_key: bytes,
    ):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO api_data(service, username, salt, nonce, api_key)
                VALUES($1, $2, $3, $4, $5)
                ON CONFLICT (service, username)
                DO UPDATE SET
                    salt = EXCLUDED.salt,
                    nonce = EXCLUDED.nonce,
                    api_key = EXCLUDED.api_key
                """,
                service,
                username,
                salt,
                nonce,
                api_key,
            )

    async def get_credentials(self, service: str, username: str):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT salt, nonce, api_key
                FROM api_data
                WHERE service = $1 AND username = $2
                """,
                service,
                username,
            )

        if row is None:
            return None

        return row["salt"], row["nonce"], row["api_key"]

    async def delete_credentials(self, service: str, username: str):
        async with self.pool.acquire() as conn:
            await conn.execute(
                '''
                DELETE FROM api_data
                WHERE service= $1 AND username= $2
                ''',
                service,
                username
            )

    async def get_list(self):
        async with self.pool.acquire() as conn:
            rows= await conn.fetch(
                '''
                SELECT service, username
                FROM api_data
                ORDER BY service, username
                '''
            )
        return [(row["service"], row["username"]) for row in rows]

    async def update_credentials(
    self,
    service: str,
    username: str,
    new_service: str | None = None,
    new_username: str | None = None,
    ) -> tuple[str, str] | None:
        updates = []
        values = [service, username]

        if new_service is not None:
            values.append(new_service)
            updates.append(f"service = ${len(values)}")

        if new_username is not None:
            values.append(new_username)
            updates.append(f"username = ${len(values)}")

        if not updates:
            raise ValueError("Provide a new service and/or username.")

        query = f"""
            UPDATE api_data
            SET {", ".join(updates)}
            WHERE service = $1 AND username = $2
            RETURNING service, username
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *values)

        if row is None:
            return None

        return row["service"], row["username"]

    async def update_key(
            self,
            service: str,
            username: str,
            salt: bytes,
            nonce: bytes,
            api_key: bytes,
        ):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE api_data
                SET salt= $1, nonce= $2, api_key= $3
                WHERE service = $4 AND username = $5
                RETURNING id
                """,
                salt,
                nonce,
                api_key,
                service,
                username
            )
        return row is not None

    async def migrate_master_password(
        self,
        current_master: str,
        new_master: str,
    ) -> int:
        vault = CryptoVault()

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("LOCK TABLE api_data IN ACCESS EXCLUSIVE MODE")
                rows = await conn.fetch(
                    "SELECT id, salt, nonce, api_key FROM api_data"
                )

                for row in rows:
                    current_key = vault.derive_key(current_master, row["salt"])
                    try:
                        plaintext = vault.decrypt(
                            row["api_key"], row["nonce"], current_key
                        )
                    except InvalidTag as exc:
                        raise MasterPasswordDecryptionError(row["id"]) from exc

                    salt = secrets.token_bytes(16)
                    nonce = secrets.token_bytes(12)
                    new_key = vault.derive_key(new_master, salt)
                    encrypted_key = vault.encrypt(plaintext, nonce, new_key)

                    await conn.execute(
                        """
                        UPDATE api_data
                        SET salt = $1, nonce = $2, api_key = $3
                        WHERE id = $4
                        """,
                        salt,
                        nonce,
                        encrypted_key,
                        row["id"],
                    )

        return len(rows)