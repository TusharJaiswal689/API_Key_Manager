import asyncio
import pyperclip


async def copy_and_secure_clear(text: str, delay_seconds: int = 15) -> None:
    pyperclip.copy(text)
    await asyncio.sleep(delay_seconds)
    if pyperclip.paste() == text:
        pyperclip.copy("")