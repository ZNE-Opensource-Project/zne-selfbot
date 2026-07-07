import asyncio
from typing import Optional

import aiosqlite


class Database:
    _instance: Optional["Database"] = None
    db: Optional[aiosqlite.Connection] = None

    def __init__(self) -> None:
        self.db = None

    @classmethod
    async def get_db(cls) -> aiosqlite.Connection:
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.db = await aiosqlite.connect("zne.db")
            cls._instance.db.row_factory = aiosqlite.Row
            await cls._instance._create_tables()
        return cls._instance.db

    async def _create_tables(self) -> None:
        if self.db is None:
            raise RuntimeError("Database connection not initialized")
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS zne_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS message_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                channel_id TEXT,
                author_id TEXT,
                content TEXT,
                timestamp REAL
            )
            """
        )
        await self.db.commit()
        cursor = await self.db.execute(
            "SELECT value FROM zne_meta WHERE key = ?", ("schema_version",)
        )
        row = await cursor.fetchone()
        if row is None:
            await self.db.execute(
                "INSERT INTO zne_meta (key, value) VALUES (?, ?)",
                ("schema_version", "1"),
            )
            await self.db.commit()
