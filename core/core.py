import asyncio
import importlib.util
import os
import sys
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands

HAS_RICH: bool = False
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    HAS_RICH = True
except ImportError:
    pass

from .database import Database
from .config import BOT


def clear_terminal() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def print_ascii_header() -> None:
    lines = [
        "███████╗███╗   ██╗███████╗",
        "╚══███╔╝████╗  ██║██╔════╝",
        "  ███╔╝ ██╔██╗ ██║█████╗  ",
        " ███╔╝  ██║╚██╗██║██╔══╝  ",
        "███████╗██║ ╚████║███████╗",
        "╚══════╝╚═╝  ╚═══╝╚══════╝",
    ]
    if HAS_RICH:
        console = Console()
        for line in lines:
            console.print(line.center(80), style="purple")
    else:
        for line in lines:
            print(line.center(80))


def prompt_text(question: str) -> str:
    if HAS_RICH:
        console = Console()
        result = console.input(f"[bold cyan]{question}[/bold cyan] ")
    else:
        result = input(question)
    return result.strip()


async def run_onboarding() -> None:
    clear_terminal()
    print_ascii_header()

    token = prompt_text("Enter your account token:")
    while not token:
        token = prompt_text("Enter your account token:")

    bot_type_raw = input("Do you want People to run your commands? (Y/N): ").strip().lower()
    if bot_type_raw == "y":
        bot_type = "user"
    else:
        bot_type = "self"

    prefix = input("Whats your desired prefix?:").strip()
    if not prefix:
        prefix = "."
    if len(prefix) > 5:
        truncated = prefix[:5]
        print(f"Prefix truncated to 5 characters: {truncated}")
        prefix = truncated

    config_content = (
        f'class BOT:\n'
        f'    TOKEN = "{token}"\n'
        f'    PREFIX = "{prefix}"\n'
        f'    BOT_TYPE = "{bot_type}"\n'
    )
    with open("config.py", "w", encoding="utf-8") as f:
        f.write(config_content)

    print("Config saved. Launching ZNE...")


def is_config_valid() -> bool:
    try:
        from config import BOT as ImportedBOT

        token = getattr(ImportedBOT, "TOKEN", "")
        if not token or len(token) < 10 or token == "MTQetc...":
            return False
        return True
    except Exception:
        return False


bot = commands.Bot(
    command_prefix=BOT.PREFIX,
    self_bot=(BOT.BOT_TYPE == "self"),
    user_bot=(BOT.BOT_TYPE == "user"),
    help_command=None,
    case_insensitive=True,
)


@bot.before_invoke
async def delete_invoke_message(ctx: commands.Context) -> None:
    try:
        await ctx.message.delete()
    except (discord.Forbidden, discord.NotFound):
        pass


@bot.event
async def on_ready() -> None:
    clear_terminal()
    print_ascii_header()
    print(f"Logged in as {bot.user} | {bot.user.id}".center(80))
    print(f"Prefix: {BOT.PREFIX} | Type: {BOT.BOT_TYPE}".center(80))
    print(f"Guilds: {len(bot.guilds)} | Commands: {len(bot.commands)}".center(80))


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author == bot.user:
        if BOT.BOT_TYPE != "self":
            return

    await log_message_to_db(message)

    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx: commands.Context, error: Exception) -> None:
    import traceback

    error_text = f"[ERROR] {traceback.format_exc()}"
    if HAS_RICH:
        console = Console()
        console.print(error_text, style="bold red")
    else:
        print(f"\033[91m{error_text}\033[0m")


async def log_message_to_db(message: discord.Message) -> None:
    try:
        db = await Database.get_db()
        await db.execute(
            """
            INSERT INTO message_log (guild_id, channel_id, author_id, content, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(getattr(message.guild, "id", None)) if message.guild else None,
                str(message.channel.id) if message.channel else None,
                str(message.author.id) if message.author else None,
                message.content or "",
                message.created_at.timestamp() if message.created_at else 0.0,
            ),
        )
        await db.commit()
    except Exception:
        pass


async def load_extensions(bot: commands.Bot) -> None:
    base_dir = Path(__file__).parent.parent
    for folder in ("core", "cogs"):
        folder_path = base_dir / folder
        if not folder_path.is_dir():
            continue
        for py_file in sorted(folder_path.glob("*.py")):
            if py_file.stem.startswith("_") or py_file.stem == "__init__":
                continue
            module_name = f"{folder}.{py_file.stem}"
            try:
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)  # type: ignore[union-attr]
                if hasattr(module, "setup"):
                    await module.setup(bot)
                    print(f"Loaded extension: {module_name}")
            except Exception as e:
                print(f"Failed to load extension {module_name}: {e}")


async def main() -> None:
    if not is_config_valid():
        await run_onboarding()

    await Database.get_db()
    await load_extensions(bot)
    await bot.start(BOT.TOKEN)
