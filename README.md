# API Key Manager

Keeping track of API keys is one of those small but persistent hassles of
developer life. Between projects, services, and usernames, I found myself
repeatedly looking up credentials and trying to remember where I had saved
them. I built API Key Manager to make that everyday workflow easier: a small
MCP server that keeps API credentials in a local PostgreSQL database and makes
them available through tools in an MCP-compatible client.

This project grew out of a practical need, and it was also a way for me to
learn by building something I would actually use. Along the way, I worked with
MCP tool definitions, asynchronous Python, PostgreSQL access with `asyncpg`,
input validation with Pydantic, and encrypting data before storing it.

## What it can do

- **Store an API key** for a service and username. If that pair already
  exists, its saved key is replaced.
- **Retrieve an API key** by copying it to the clipboard. The clipboard is
  cleared after 15 seconds if its contents have not changed.
- **Replace an existing API key** without changing its service or username.
- **Migrate the master password** by decrypting and re-encrypting all saved keys.
- **Rename a stored service and/or username.**
- **Delete a stored API key.**
- **List the services and usernames** that have saved keys.

API keys are encrypted with AES-GCM before being written to PostgreSQL. The
encryption key is derived from the `MASTER` value using PBKDF2-HMAC-SHA256 and
a per-record salt. The master value is supplied through the environment; it
is not stored in the database. If retrieval cannot decrypt a saved key, the
tool asks you to check `MASTER`; damaged encrypted data can cause the same
decryption failure.

## Requirements

- Python 3.14 or newer
- PostgreSQL
- [uv](https://docs.astral.sh/uv/) for installing and running the project
- A desktop session for tools that prompt for an API key or interact with the
  clipboard

## Set up PostgreSQL

Create a PostgreSQL user and database. For example, from `psql` as a
PostgreSQL administrator:

```sql
CREATE USER apikeymanager WITH PASSWORD 'choose-a-password';
CREATE DATABASE apikeymanager OWNER apikeymanager;
```

The application creates its `api_data` table automatically when it first
connects. The table has a unique constraint on the service and username pair.

## Install and configure

Clone the repository and enter its directory:

```sh
git clone https://github.com/TusharJaiswal689/API_Key_Manager.git
cd API_Key_Manager
```

Create a `.env` file in the project root:

```dotenv
DB_DRIVER=postgresql
DB_USER=apikeymanager
DB_PASS=choose-a-password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=apikeymanager
MASTER=choose-a-strong-master-password
```

Install the project dependencies:

```sh
uv sync
```

The `.env` file contains database credentials and the master password. Keep
it private and do not commit it to source control.

## Connect it to an MCP client

The server uses the MCP `stdio` transport. In an MCP client that supports
stdio servers, configure it to launch the project with `uv`:

```json
{
  "servers": {
    "api-key-manager": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/API_Key_Manager",
        "run",
        "apikeymanager"
      ]
    }
  }
}
```

Replace `/absolute/path/to/API_Key_Manager` with the path where you cloned
the repository. MCP client configuration formats can vary; use the equivalent
stdio server configuration for your client. Restart or reconnect the server
after changing the configuration or adding tools.

## Available MCP tools

| Tool | Purpose |
| --- | --- |
| `store_key` | Prompt for a key and save it for a service and username. |
| `retrieve_key` | Copy the saved key for a service and username to the clipboard. |
| `update_key` | Prompt for a replacement key for an existing service and username. |
| `update_credentials` | Change the service name, username, or both for an existing record. |
| `migrate_master_password` | Re-encrypt saved keys with a new master password. |
| `delete_key` | Delete the record for a service and username. |
| `get_all_service` | List the saved service and username pairs. |

The store and update-key tools use a native Tkinter dialog to collect the
secret rather than requiring the API key to be passed as a tool argument.
That means those tools need access to a graphical desktop on the machine
running the MCP server.

To migrate the master password, invoke `migrate_master_password` while the
server is still configured with the current `MASTER`. The tool prompts for the
new password twice and re-encrypts all saved keys as one database transaction.
After it succeeds, update `MASTER` in `.env` (or your deployment environment)
to the new value before restarting the server. The running process switches to
the new password after migration. If a stored key cannot be decrypted, the
tool reports its record ID and explains that the current `MASTER` may be wrong
or the encrypted record may be damaged; the database transaction rolls back
without changing any records.

## A note about the learning process

I built this to solve a real quality-of-life problem, but the implementation
also gave me a hands-on path through several parts of application development:
designing a useful tool interface, working with async database operations,
handling secrets and validation, and connecting a local application to an MCP
client. It is intentionally a focused project: a practical utility that I
can keep improving as I learn.