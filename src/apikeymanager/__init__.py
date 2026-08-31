import asyncio
import sys
import secrets
import tkinter as tk
from tkinter import messagebox, simpledialog
from pathlib import Path
from mcp.server.fastmcp import FastMCP

from apikeymanager.config import master
from apikeymanager.crypto import CryptoVault
from apikeymanager.clipboard import copy_and_secure_clear
from apikeymanager.db import DatabaseManager
from apikeymanager.schemas import apikey_retrieve, apikey_store

vault = CryptoVault()
pool_lock = asyncio.Lock()
mcp = FastMCP("API Key Manager")
db = DatabaseManager()


def get_apikey() -> str:
    root = tk.Tk()

    try:
        while True:
            key = simpledialog.askstring(
                "API Key Manager", "Enter API Key", show="*"
            )

            if key is None:
                raise ValueError("Cancelled by user.")
            if key.strip():
                return key

            messagebox.showerror("API Key Manager", "API key cannot be empty.")
    finally:
        root.destroy()


async def get_pool() -> None:
    if db.pool is None:
        async with pool_lock:
            if db.pool is None:
                await db.connect()
                await db.setup_database()


@mcp.tool()
async def store_key(params: apikey_store) -> str:
    await get_pool()
    key = get_apikey()

    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    secret_key = vault.derive_key(master, salt)
    encoded_key = vault.encrypt(key, nonce, secret_key)

    await db.save_credentials(
        service=params.service,
        username=params.username,
        salt=salt,
        nonce=nonce,
        api_key=encoded_key,
    )
    return (
        f"Successfully added the API key for service {params.service} "
        f"and username {params.username}."
    )


@mcp.tool()
async def retrieve_key(params: apikey_retrieve) -> str:
    await get_pool()
    record = await db.get_credentials(
        service=params.service,
        username=params.username,
    )

    if not record:
        return "No API key exists for the given service and username."

    salt, nonce, encoded_key = record
    secret_key = vault.derive_key(master, salt)
    decoded_key = vault.decrypt(encoded_key, nonce, secret_key)
    await copy_and_secure_clear(decoded_key)

    return "The API key has been copied to your clipboard."


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
