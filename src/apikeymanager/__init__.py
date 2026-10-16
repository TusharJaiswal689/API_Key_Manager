import asyncio
import sys
import secrets
import tkinter as tk
from tkinter import messagebox, simpledialog
from pathlib import Path
from cryptography.exceptions import InvalidTag
from mcp.server.fastmcp import FastMCP

from apikeymanager.config import master
from apikeymanager.crypto import CryptoVault
from apikeymanager.clipboard import copy_and_secure_clear
from apikeymanager.db import DatabaseManager, MasterPasswordDecryptionError
from apikeymanager.schemas import apikey_credentials, apikey_credentials_update

vault = CryptoVault()
pool_lock = asyncio.Lock()
credential_lock = asyncio.Lock()
mcp = FastMCP("API Key Manager")
db = DatabaseManager()


def get_apikey() -> str:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    try:
        while True:
            key = simpledialog.askstring(
                "API Key Manager", "Enter API Key", show="*", parent=root
            )

            if key is None:
                raise ValueError("Cancelled by user.")
            if key.strip():
                return key

            messagebox.showerror("API Key Manager", "API key cannot be empty.")
    finally:
        root.destroy()


def get_new_master_password() -> str | None:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    try:
        while True:
            new_master = simpledialog.askstring(
                "API Key Manager",
                "Enter the new master password",
                show="*",
                parent=root,
            )
            if new_master is None:
                return None
            if not new_master.strip():
                messagebox.showerror(
                    "API Key Manager",
                    "Master password cannot be empty.",
                    parent=root,
                )
                continue

            confirmation = simpledialog.askstring(
                "API Key Manager",
                "Confirm the new master password",
                show="*",
                parent=root,
            )
            if confirmation is None:
                return None
            if new_master != confirmation:
                messagebox.showerror(
                    "API Key Manager",
                    "The master passwords do not match.",
                    parent=root,
                )
                continue

            return new_master
    finally:
        root.destroy()


async def get_pool() -> None:
    if db.pool is None:
        async with pool_lock:
            if db.pool is None:
                await db.connect()
                await db.setup_database()


@mcp.tool()
async def store_key(params: apikey_credentials) -> str:
    await get_pool()
    key = get_apikey()

    async with credential_lock:
        salt = secrets.token_bytes(16)
        nonce = secrets.token_bytes(12)
        secret_key = vault.derive_key(master, salt)
        encoded_key = vault.encrypt(key, nonce, secret_key)

        await db.save_credentials(
            service=params.service.lower(),
            username=params.username.lower(),
            salt=salt,
            nonce=nonce,
            api_key=encoded_key,
        )
    return (
        f"Successfully added the API key for service {params.service} "
        f"and username {params.username}."
    )


@mcp.tool()
async def retrieve_key(params: apikey_credentials) -> str:
    if master is None:
        return "MASTER is not configured, so the API key cannot be decrypted."

    await get_pool()
    async with credential_lock:
        record = await db.get_credentials(
            service=params.service.lower(),
            username=params.username.lower(),
        )

        if not record:
            return "No API key exists for the given service and username."

        salt, nonce, encoded_key = record
        secret_key = vault.derive_key(master, salt)
        try:
            decoded_key = vault.decrypt(encoded_key, nonce, secret_key)
        except InvalidTag:
            return (
                "Unable to decrypt this API key. Check that MASTER in your "
                "environment matches the password used to encrypt it. The "
                "stored encrypted data may also be damaged."
            )

    await copy_and_secure_clear(decoded_key)

    return "The API key has been copied to your clipboard."

@mcp.tool()
async def delete_key(params: apikey_credentials) -> str:
    service= params.service.lower()
    username=params.username.lower()
    await get_pool()
    async with credential_lock:
        record= await db.get_credentials(service, username)
        if not record:
            return "No API key exists for the given service and username."

        await db.delete_credentials(service, username)
    return f"API key for {service} with username: {username} has been deleted."

@mcp.tool()
async def get_all_service():
    await get_pool()
    rows = await db.get_list()

    if not rows:
        return "No services or usernames are stored."
    return "\n".join(f"{service} - {username}" for service, username in rows)

@mcp.tool()
async def update_credentials(params: apikey_credentials_update) -> str:
    if params.new_service is None and params.new_username is None:
        return "Please provide a new service and/or username."

    await get_pool()

    updated = await db.update_credentials(
        service=params.service,
        username=params.username,
        new_service=params.new_service,
        new_username=params.new_username,
    )

    if updated is None:
        return "No API key exists for the given service and username."

    updated_service, updated_username = updated
    return (
        f"Updated API key details.\nservice: {updated_service}; "
        f"username: {updated_username}."
    )

@mcp.tool()
async def update_key(params: apikey_credentials) -> str:
    await get_pool()
    service= params.service.lower()
    username= params.username.lower()

    async with credential_lock:
        record = await db.get_credentials(service, username)
        if not record:
            return "No API record exists for the given service and username."

    key = get_apikey()

    async with credential_lock:
        salt = secrets.token_bytes(16)
        nonce = secrets.token_bytes(12)
        secret_key = vault.derive_key(master, salt)
        encoded_key = vault.encrypt(key, nonce, secret_key)

        updated = await db.update_key(
            service=service,
            username=username,
            salt=salt,
            nonce=nonce,
            api_key=encoded_key,
        )
    if not updated:
        return "No API record exists for the given service and username."
    return (
        f"Successfully updated the API key for service {params.service} "
        f"and username {params.username}."
    )

@mcp.tool()
async def migrate_master_password() -> str:
    global master

    if master is None:
        return "MASTER is not configured, so the migration cannot run."

    await get_pool()
    new_master = get_new_master_password()
    if new_master is None:
        return "Master password migration cancelled."

    async with credential_lock:
        try:
            migrated_count = await db.migrate_master_password(master, new_master)
        except MasterPasswordDecryptionError as exc:
            return (
                "Master password migration failed: the configured MASTER could "
                f"not decrypt record {exc.record_id}. It may be incorrect, or "
                "that record's encrypted data may be damaged. The database "
                "transaction was rolled back, so no records were changed. "
                "Verify that MASTER is still the password used to encrypt these "
                "keys, then try again."
            )

        master = new_master

    return (
        f"Successfully re-encrypted {migrated_count} API key(s). "
        "Update MASTER in your environment configuration before restarting "
        "the MCP server. The running server is now using the new master."
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
