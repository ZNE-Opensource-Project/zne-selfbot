import asyncio
import logging
import re

import queue
import sys
import threading
import time
from datetime import datetime
from flask import Flask, Response, render_template, jsonify, request

import discord
import discord
from config import BOT
from .commands_catalog import COMMAND_CATALOG

logging.getLogger("werkzeug").setLevel(logging.ERROR)

app = Flask(__name__)

bot_instance = None


def set_bot(bot) -> None:
    global bot_instance
    bot_instance = bot


def get_commands():
    if bot_instance is None:
        return {}
    grouped = {}
    for command in bot_instance.commands:
        cog = command.cog.__class__.__name__ if command.cog else "No Category"
        if cog not in grouped:
            grouped[cog] = []
        grouped[cog].append(command.name)
    for cog in grouped:
        grouped[cog].sort()
    return dict(sorted(grouped.items()))


def _pick_recipient():
    me = bot_instance.user
    for rel in getattr(bot_instance, "friends", []):
        if getattr(rel, "type", None) == discord.RelationshipType.friend:
            user = getattr(rel, "user", None)
            if user is not None and user.id != me.id:
                return user.id
    for guild in bot_instance.guilds:
        for member in guild.members:
            if member.id != me.id and not member.bot:
                return member.id
    return None


async def _resolve_test_group():
    me = bot_instance.user
    for ch in bot_instance.private_channels:
        if ch.type == discord.ChannelType.group and ch.name == "TEST":
            return ch

    recipient = _pick_recipient()
    channel = await bot_instance.http.start_group([me.id, recipient] if recipient else [me.id])
    await asyncio.sleep(1)
    ch = bot_instance.get_channel(channel["id"])
    if ch is None:
        ch = await bot_instance.fetch_channel(channel["id"])
    try:
        await ch.edit(name="TEST")
    except Exception:
        pass
    if recipient is not None:
        try:
            await bot_instance.http.remove_group_recipient(ch.id, recipient)
        except Exception:
            pass
    return ch


async def _invoke_in_test(command_name, args=""):
    channel = await _resolve_test_group()
    if channel is None:
        raise RuntimeError("Could not resolve TEST group chat.")
    content = f"{BOT.PREFIX}{command_name}"
    if args and args.strip():
        content += " " + args.strip()
    params = discord.http.handle_message_parameters(content=content)
    msg = await bot_instance.http.send_message(channel.id, params=params)
    fetched = await channel.fetch_message(int(msg["id"]))
    await bot_instance.process_commands(fetched)
    return channel.id


def execute_command(command_name, args=""):
    if bot_instance is None:
        return {"ok": False, "error": "Bot is not running."}
    if bot_instance.get_command(command_name) is None:
        return {"ok": False, "error": f"Unknown command: {command_name}"}
    try:
        future = asyncio.run_coroutine_threadsafe(
            _invoke_in_test(command_name, args), bot_instance.loop
        )
        channel_id = future.result(timeout=30)
        return {"ok": True, "channel_id": channel_id}
    except Exception as e:
        return {"ok": False, "error": str(e)}

import os

log_queue = queue.Queue()
max_logs = 500

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ZNE", "Logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "webui_console.log")
max_log_lines = 500

bot_stats = {
    "username": "Loading...",
    "avatar_url": None,
    "guilds": 0,
    "commands": 0,
    "uptime": "00:00:00",
    "version": "ZNE V3",
    "start_time": None,
}

_original_stdout = sys.stdout
_original_stderr = sys.stderr

ansi_pattern = re.compile(r'\x1b\[[0-9;]*m')


class LogCapture:
    def write(self, text):
        if text and text.strip():
            clean = ansi_pattern.sub('', text)
            log_queue.put(clean)
            try:
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(clean + "\n")
                self._trim_log_file()
            except Exception:
                pass
            if log_queue.qsize() > max_logs:
                try:
                    while log_queue.qsize() > max_logs:
                        log_queue.get_nowait()
                except queue.Empty:
                    pass

    def _trim_log_file(self):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if len(lines) > max_log_lines:
                with open(LOG_FILE, "w", encoding="utf-8") as f:
                    f.writelines(lines[-max_log_lines:])
        except Exception:
            pass

    def flush(self):
        pass

    def isatty(self):
        return False


class Tee:
    def __init__(self, original, capture):
        self.original = original
        self.capture = capture

    def write(self, text):
        self.original.write(text)
        self.capture.write(text)

    def flush(self):
        self.original.flush()
        self.capture.flush()

    def isatty(self):
        return self.original.isatty()


log_capture = LogCapture()


def update_stats(**kwargs):
    for key, value in kwargs.items():
        if key in bot_stats:
            bot_stats[key] = value


def read_recent_logs(limit=max_log_lines):
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f.readlines()]
        return lines[-limit:]
    except Exception:
        return []


def redirect_output():
    sys.stdout = Tee(_original_stdout, log_capture)
    sys.stderr = Tee(_original_stderr, log_capture)


def _run_flask():
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)


def start_webui(bot=None):
    if bot is not None:
        set_bot(bot)
    redirect_output()
    thread = threading.Thread(target=_run_flask, daemon=True)
    thread.start()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/commands")
def commands():
    return render_template("commands.html", command_groups=get_commands())


@app.route("/api/command/<name>")
def api_command(name):
    entry = dict(COMMAND_CATALOG.get(name, {}))
    entry["name"] = name
    entry["exists"] = bot_instance is not None and bot_instance.get_command(name) is not None
    if not entry.get("category"):
        entry["category"] = "No Category"
    return jsonify(entry)


@app.route("/api/execute", methods=["POST"])
def api_execute():
    data = request.get_json(silent=True) or {}
    name = data.get("command", "").strip()
    args = data.get("args", "")
    if not name:
        return jsonify({"ok": False, "error": "No command provided."})
    return jsonify(execute_command(name, args))


@app.route("/stats")
def stats():
    stats_data = dict(bot_stats)
    if bot_stats.get("start_time"):
        elapsed = time.time() - bot_stats["start_time"]
        hours, rem = divmod(int(elapsed), 3600)
        minutes, seconds = divmod(rem, 60)
        stats_data["uptime"] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return jsonify(stats_data)


@app.route("/api/logs")
def api_logs():
    return jsonify({"logs": read_recent_logs()})


@app.route("/stream")
def stream():
    def event_stream():
        while True:
            try:
                msg = log_queue.get(timeout=1)
                for line in msg.split("\n"):
                    yield f"data: {line}\n"
                yield "\n"
            except queue.Empty:
                yield ": heartbeat\n\n"

    return Response(event_stream(), mimetype="text/event-stream")
