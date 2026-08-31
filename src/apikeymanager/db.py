import asyncpg
from apikeymanager.config import db_url


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
