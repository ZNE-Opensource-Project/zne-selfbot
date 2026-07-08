import asyncio
import csv
import datetime
import io
import json
import os
import re
import traceback

import aiohttp
import discord
from discord.ext import commands
from typing import Optional, List, Set

DUMPS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ZNE", "Dumps")
os.makedirs(DUMPS_DIR, exist_ok=True)

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".tiff", ".ico")
VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv", ".flv", ".m4v", ".3gp")
AUDIO_EXTENSIONS = (".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a", ".wma", ".opus")
TEXT_EXTENSIONS = (
    ".txt", ".log", ".csv", ".json", ".xml", ".yaml", ".yml", ".md", ".cfg",
    ".ini", ".py", ".js", ".html", ".css", ".sql", ".sh", ".bat", ".ps1", ".toml",
)


class DumpCommands(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot: commands.Bot = bot
        self.dump_lock: asyncio.Lock = asyncio.Lock()
        self._active_dumps: Set[int] = set()

    async def _delete_invoke(self, ctx: commands.Context) -> None:
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass

    async def _safe_send(self, ctx: commands.Context, content: str) -> discord.Message | None:
        try:
            return await ctx.send(content)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
            print(f"[DumpCommands] send failed: {e}")
            return None

    def _sanitize_filename(self, name: str) -> str:
        invalid = r'[<>:"/\\|?*]'
        sanitized = re.sub(invalid, '_', name)
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', sanitized)
        return sanitized[:200].strip()

    async def _send_progress(self, msg: discord.Message, current: int, total: int, label: str) -> None:
        if total == 0:
            pct = 100
        else:
            pct = int((current / total) * 100)
        bar_len = 20
        filled = int(bar_len * current / max(total, 1))
        bar = '█' * filled + '░' * (bar_len - filled)
        content = f"**{label}**\n`[{bar}]` {pct}%\n{current}/{total} items processed"
        try:
            await msg.edit(content=content)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass

    async def _throttled_progress(self, msg: discord.Message, current: int, total: int, label: str,
                                  last_edit: list) -> None:
        now = asyncio.get_event_loop().time()
        if now - last_edit[0] >= 2.0 or current >= total:
            last_edit[0] = now
            await self._send_progress(msg, current, total, label)

    async def _download_file(self, url: str, filepath: str) -> bool:
        try:
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        with open(filepath, 'wb') as f:
                            f.write(await resp.read())
                        return True
            return False
        except Exception:
            return False

    async def _fetch_all_messages(self, channel, limit: Optional[int] = None) -> list:
        messages = []
        last_id = None
        while True:
            kwargs = {"limit": 100}
            if last_id:
                kwargs["before"] = discord.Object(id=last_id)
            batch = []
            try:
                async for msg in channel.history(**kwargs):
                    batch.append(msg)
                    last_id = msg.id
                    if limit and len(messages) + len(batch) >= limit:
                        break
            except (discord.Forbidden, discord.HTTPException) as e:
                raise e
            if not batch:
                break
            messages.extend(batch)
            if limit and len(messages) >= limit:
                messages = messages[:limit]
                break
            await asyncio.sleep(0.5)
        return messages

    def _create_dump_dir(self, *subdirs) -> str:
        path = os.path.join(DUMPS_DIR, *subdirs)
        os.makedirs(path, exist_ok=True)
        return path

    def _timestamp(self) -> str:
        return datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    def _guild_sub(self, guild: Optional[discord.Guild]) -> str:
        if guild is None:
            return "DM"
        return f"{self._sanitize_filename(guild.name)}_{guild.id}"

    def _channel_sub(self, channel: discord.TextChannel) -> str:
        return f"{self._sanitize_filename(channel.name)}_{channel.id}"

    async def _resolve_channel(self, ctx: commands.Context, channel_ref: Optional[str]):
        if channel_ref is None:
            return ctx.channel
        try:
            cid = int(re.sub(r"[<#>]", "", channel_ref))
            ch = self.bot.get_channel(cid) or ctx.guild.get_channel(cid) if ctx.guild else self.bot.get_channel(cid)
            return ch
        except (ValueError, AttributeError):
            if ctx.guild:
                return discord.utils.get(ctx.guild.text_channels, name=channel_ref)
        return None

    async def _resolve_guild(self, ctx: commands.Context, guild_ref: Optional[str]) -> Optional[discord.Guild]:
        if guild_ref is None:
            return ctx.guild
        try:
            gid = int(guild_ref)
            return self.bot.get_guild(gid)
        except ValueError:
            return discord.utils.get(self.bot.guilds, name=guild_ref)

    def _ext_for_url(self, filename: str, content_type: Optional[str]) -> str:
        base, ext = os.path.splitext(filename)
        if ext:
            return ext.lower()
        if content_type:
            mapping = {
                "image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
                "image/webp": ".webp", "video/mp4": ".mp4", "audio/mpeg": ".mp3",
                "audio/ogg": ".ogg", "audio/wav": ".wav",
            }
            return mapping.get(content_type.lower(), "")
        return ""

    # ------------------------------------------------------------------ #
    # 1. dumpall
    # ------------------------------------------------------------------ #
    @commands.command(name="dumpall")
    async def dumpall(self, ctx: commands.Context, channel: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        target = await self._resolve_channel(ctx, channel)
        if target is None:
            await self._safe_send(ctx, "❌ Channel not found.")
            return
        if target.id in self._active_dumps:
            await self._safe_send(ctx, "A dump is already in progress for this channel. Wait for it to complete.")
            return

        status = await self._safe_send(ctx, "🔍 Scanning messages...")
        if status is None:
            return
        self._active_dumps.add(target.id)
        try:
            messages = await self._fetch_all_messages(target)
            total = len(messages)
            base = self._create_dump_dir(
                self._guild_sub(target.guild),
                self._channel_sub(target),
                f"messages_{self._timestamp()}",
            )
            last_edit = [0.0]
            msg_data: List[dict] = []
            txt_lines: List[str] = []
            for i, msg in enumerate(messages, 1):
                try:
                    attachments = [{"url": a.url, "filename": a.filename, "size": a.size} for a in msg.attachments]
                    embeds = [{"title": e.title, "description": e.description, "url": e.url} for e in msg.embeds]
                    reactions = [{"emoji": str(r.emoji), "count": r.count} for r in msg.reactions]
                    msg_data.append({
                        "id": str(msg.id),
                        "author_id": str(msg.author.id),
                        "author_name": msg.author.name,
                        "content": msg.content,
                        "timestamp": msg.created_at.isoformat() if msg.created_at else None,
                        "edited_timestamp": msg.edited_at.isoformat() if msg.edited_at else None,
                        "attachments": attachments,
                        "embeds": embeds,
                        "reactions": reactions,
                        "pinned": msg.pinned,
                        "type": str(msg.type),
                    })
                    ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S") if msg.created_at else "?"
                    txt_lines.append(f"[{ts}] {msg.author}: {msg.content}")
                except Exception:
                    continue
                if i % 500 == 0:
                    await self._throttled_progress(status, i, total, "📝 Dumping messages", last_edit)

            structure = {
                "channel_id": str(target.id),
                "channel_name": getattr(target, "name", "DM"),
                "guild_id": str(target.guild.id) if target.guild else None,
                "guild_name": target.guild.name if target.guild else None,
                "dump_date": datetime.datetime.now().isoformat(),
                "total_messages": len(msg_data),
                "messages": msg_data,
            }
            with open(os.path.join(base, "messages.json"), "w", encoding="utf-8") as f:
                json.dump(structure, f, ensure_ascii=False, indent=2)
            with open(os.path.join(base, "messages.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(txt_lines))

            await self._send_progress(status, total, total, "✅ Dump complete")
            await status.edit(content=f"✅ Dump complete. {len(msg_data)} messages saved to `{base}`")
        except (discord.Forbidden, discord.HTTPException) as e:
            try:
                await status.edit(content=f"❌ Dump failed: {e}")
            except Exception:
                pass
        except OSError:
            try:
                await status.edit(content="❌ Disk full or write error.")
            except Exception:
                pass
        except Exception as e:
            print(traceback.format_exc())
            try:
                await status.edit(content=f"❌ Dump failed: {e}")
            except Exception:
                pass
        finally:
            self._active_dumps.discard(target.id)

    # ------------------------------------------------------------------ #
    # Generic attachment dump
    # ------------------------------------------------------------------ #
    async def _dump_attachments(self, ctx, target, label, extensions, content_prefixes,
                                dir_suffix, max_count, progress_every, msg_edit_every,
                                manifest_extra=None, type_filter=None):
        status = await self._safe_send(ctx, f"🔍 Scanning {label}...")
        if status is None:
            return
        self._active_dumps.add(target.id)
        await self._send_progress(status, 0, max_count, f"🔍 Scanning {label}")
        try:
            async with self.dump_lock:
                base = self._create_dump_dir(
                    self._guild_sub(target.guild),
                    self._channel_sub(target),
                    f"{dir_suffix}_{self._timestamp()}",
                )
            found = 0
            downloaded = 0
            failed = 0
            skipped = 0
            seen_urls: Set[str] = set()
            seen_ids: Set[int] = set()
            manifest: List[dict] = []
            last_edit = [0.0]
            total_estimate = max_count

            async for msg in target.history(limit=None):
                if found >= max_count:
                    break
                for att in msg.attachments:
                    if found >= max_count:
                        break
                    url = att.url
                    fname = att.filename
                    ctype = getattr(att, "content_type", None)
                    ext = self._ext_for_url(fname, ctype)

                    if type_filter is not None:
                        if not type_filter(fname, ctype, ext):
                            continue
                    else:
                        if extensions and ext not in extensions:
                            continue
                        if content_prefixes and ctype:
                            if not any(ctype.startswith(p) for p in content_prefixes):
                                if ext not in extensions:
                                    continue

                    found += 1

                    if url in seen_urls:
                        skipped += 1
                        continue
                    seen_urls.add(url)

                    if getattr(att, "id", None) is not None and att.id in seen_ids:
                        skipped += 1
                        continue
                    if getattr(att, "id", None) is not None:
                        seen_ids.add(att.id)

                    dl_name = f"{msg.id}_{self._sanitize_filename(fname) or att.id}{ext}"
                    if not os.path.splitext(dl_name)[1] and ext:
                        dl_name = f"{msg.id}_{att.id}{ext}"
                    filepath = os.path.join(base, dl_name)
                    ok = await self._download_file(url, filepath)
                    await asyncio.sleep(0.1)
                    if ok:
                        downloaded += 1
                        entry = {
                            "filename": dl_name,
                            "original_url": url,
                            "message_id": str(msg.id),
                            "author": msg.author.name,
                            "author_id": str(msg.author.id),
                            "size": att.size,
                            "content_type": ctype,
                        }
                        if manifest_extra:
                            entry.update(manifest_extra(att))
                        manifest.append(entry)
                    else:
                        failed += 1

                    if found % progress_every == 0:
                        await self._throttled_progress(status, found, total_estimate,
                                                       f"📥 Downloading {label}", last_edit)

            with open(os.path.join(base, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)

            await status.edit(
                content=(f"✅ {label} dump complete.\n"
                         f"Found: {found}\nDownloaded: {downloaded}\n"
                         f"Failed: {failed}\nSkipped (dupes): {skipped}\n"
                         f"Saved to `{base}`")
            )
        except (discord.Forbidden, discord.HTTPException) as e:
            try:
                await status.edit(content=f"❌ Dump failed: {e}")
            except Exception:
                pass
        except OSError:
            try:
                await status.edit(content="❌ Disk full or write error.")
            except Exception:
                pass
        except Exception as e:
            print(traceback.format_exc())
            try:
                await status.edit(content=f"❌ Dump failed: {e}")
            except Exception:
                pass
        finally:
            self._active_dumps.discard(target.id)

    def _type_matcher(self, extensions, content_prefixes):
        def matcher(fname, ctype, ext):
            if ext in extensions:
                return True
            if ctype and any(ctype.startswith(p) for p in content_prefixes):
                return True
            return False
        return matcher

    # ------------------------------------------------------------------ #
    # 2. dumpimages
    # ------------------------------------------------------------------ #
    @commands.command(name="dumpimages")
    async def dumpimages(self, ctx: commands.Context, channel: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        target = await self._resolve_channel(ctx, channel)
        if target is None:
            await self._safe_send(ctx, "❌ Channel not found.")
            return
        if target.id in self._active_dumps:
            await self._safe_send(ctx, "A dump is already in progress for this channel. Wait for it to complete.")
            return
        matcher = self._type_matcher(IMAGE_EXTENSIONS, ["image/"])
        await self._dump_attachments(ctx, target, "images", IMAGE_EXTENSIONS, ["image/"],
                                     "images", 10000, 10, 2, type_filter=matcher)

    # ------------------------------------------------------------------ #
    # 3. dumpvideos
    # ------------------------------------------------------------------ #
    @commands.command(name="dumpvideos")
    async def dumpvideos(self, ctx: commands.Context, channel: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        target = await self._resolve_channel(ctx, channel)
        if target is None:
            await self._safe_send(ctx, "❌ Channel not found.")
            return
        if target.id in self._active_dumps:
            await self._safe_send(ctx, "A dump is already in progress for this channel. Wait for it to complete.")
            return
        matcher = self._type_matcher(VIDEO_EXTENSIONS, ["video/"])
        await self._dump_attachments(ctx, target, "videos", VIDEO_EXTENSIONS, ["video/"],
                                     "videos", 1000, 5, 2, type_filter=matcher)

    # ------------------------------------------------------------------ #
    # 4. dumpaudio
    # ------------------------------------------------------------------ #
    @commands.command(name="dumpaudio")
    async def dumpaudio(self, ctx: commands.Context, channel: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        target = await self._resolve_channel(ctx, channel)
        if target is None:
            await self._safe_send(ctx, "❌ Channel not found.")
            return
        if target.id in self._active_dumps:
            await self._safe_send(ctx, "A dump is already in progress for this channel. Wait for it to complete.")
            return
        matcher = self._type_matcher(AUDIO_EXTENSIONS, ["audio/"])
        await self._dump_attachments(ctx, target, "audio", AUDIO_EXTENSIONS, ["audio/"],
                                     "audio", 5000, 10, 2, type_filter=matcher)

    # ------------------------------------------------------------------ #
    # 5. dumptext
    # ------------------------------------------------------------------ #
    @commands.command(name="dumptext")
    async def dumptext(self, ctx: commands.Context, channel: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        target = await self._resolve_channel(ctx, channel)
        if target is None:
            await self._safe_send(ctx, "❌ Channel not found.")
            return
        if target.id in self._active_dumps:
            await self._safe_send(ctx, "A dump is already in progress for this channel. Wait for it to complete.")
            return
        text_prefixes = ["text/", "application/json", "application/xml", "application/javascript"]
        matcher = self._type_matcher(TEXT_EXTENSIONS, text_prefixes)
        await self._dump_attachments(ctx, target, "text files", TEXT_EXTENSIONS, text_prefixes,
                                     "text", 10000, 10, 2, type_filter=matcher)

    # ------------------------------------------------------------------ #
    # 6. dumpattachments
    # ------------------------------------------------------------------ #
    @commands.command(name="dumpattachments")
    async def dumpattachments(self, ctx: commands.Context, channel: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        target = await self._resolve_channel(ctx, channel)
        if target is None:
            await self._safe_send(ctx, "❌ Channel not found.")
            return
        if target.id in self._active_dumps:
            await self._safe_send(ctx, "A dump is already in progress for this channel. Wait for it to complete.")
            return

        status = await self._safe_send(ctx, "🔍 Scanning attachments...")
        if status is None:
            return
        self._active_dumps.add(target.id)
        try:
            async with self.dump_lock:
                base = self._create_dump_dir(
                    self._guild_sub(target.guild),
                    self._channel_sub(target),
                    f"attachments_{self._timestamp()}",
                )
            downloaded = 0
            failed = 0
            skipped = 0
            found = 0
            seen_ids: Set[int] = set()
            manifest: List[dict] = []
            last_edit = [0.0]

            async for msg in target.history(limit=None):
                if found >= 50000:
                    break
                for att in msg.attachments:
                    if found >= 50000:
                        break
                    found += 1
                    if att.id in seen_ids:
                        skipped += 1
                        continue
                    seen_ids.add(att.id)
                    ext = self._ext_for_url(att.filename, att.content_type)
                    dl_name = f"{msg.id}_{self._sanitize_filename(att.filename) or att.id}{ext}"
                    if not os.path.splitext(dl_name)[1] and ext:
                        dl_name = f"{msg.id}_{att.id}{ext}"
                    filepath = os.path.join(base, dl_name)
                    ok = await self._download_file(att.url, filepath)
                    await asyncio.sleep(0.1)
                    if ok:
                        downloaded += 1
                        manifest.append({
                            "filename": dl_name,
                            "original_url": att.url,
                            "message_id": str(msg.id),
                            "author": msg.author.name,
                            "author_id": str(msg.author.id),
                            "size": att.size,
                            "content_type": getattr(att, "content_type", None),
                            "width": getattr(att, "width", None),
                            "height": getattr(att, "height", None),
                        })
                    else:
                        failed += 1
                    if found % 50 == 0:
                        await self._throttled_progress(status, found, 50000,
                                                       "📎 Downloading attachments", last_edit)

            with open(os.path.join(base, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)

            await status.edit(
                content=(f"✅ Attachments dump complete.\n"
                         f"Found: {found}\nDownloaded: {downloaded}\n"
                         f"Failed: {failed}\nSkipped (dupes): {skipped}\n"
                         f"Saved to `{base}`")
            )
        except (discord.Forbidden, discord.HTTPException) as e:
            try:
                await status.edit(content=f"❌ Dump failed: {e}")
            except Exception:
                pass
        except OSError:
            try:
                await status.edit(content="❌ Disk full or write error.")
            except Exception:
                pass
        except Exception as e:
            print(traceback.format_exc())
            try:
                await status.edit(content=f"❌ Dump failed: {e}")
            except Exception:
                pass
        finally:
            self._active_dumps.discard(target.id)

    # ------------------------------------------------------------------ #
    # 7. dumpfiletype
    # ------------------------------------------------------------------ #
    @commands.command(name="dumpfiletype")
    async def dumpfiletype(self, ctx: commands.Context, extension: str, channel: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        target = await self._resolve_channel(ctx, channel)
        if target is None:
            await self._safe_send(ctx, "❌ Channel not found.")
            return
        if target.id in self._active_dumps:
            await self._safe_send(ctx, "A dump is already in progress for this channel. Wait for it to complete.")
            return
        ext = extension.lower().lstrip(".")
        want = f".{ext}"

        status = await self._safe_send(ctx, f"🔍 Scanning .{ext} files...")
        if status is None:
            return
        self._active_dumps.add(target.id)
        try:
            async with self.dump_lock:
                base = self._create_dump_dir(
                    self._guild_sub(target.guild),
                    self._channel_sub(target),
                    f"{ext}_{self._timestamp()}",
                )
            downloaded = 0
            failed = 0
            found = 0
            seen_ids: Set[int] = set()
            manifest: List[dict] = []
            last_edit = [0.0]

            async for msg in target.history(limit=None):
                if found >= 5000:
                    break
                for att in msg.attachments:
                    if found >= 5000:
                        break
                    if not att.filename.lower().endswith(want):
                        continue
                    found += 1
                    if att.id in seen_ids:
                        continue
                    seen_ids.add(att.id)
                    dl_name = f"{msg.id}_{self._sanitize_filename(att.filename) or att.id}"
                    filepath = os.path.join(base, dl_name)
                    ok = await self._download_file(att.url, filepath)
                    await asyncio.sleep(0.1)
                    if ok:
                        downloaded += 1
                        manifest.append({
                            "filename": dl_name,
                            "original_url": att.url,
                            "message_id": str(msg.id),
                            "author": msg.author.name,
                            "author_id": str(msg.author.id),
                            "size": att.size,
                        })
                    else:
                        failed += 1
                    if found % 50 == 0:
                        await self._throttled_progress(status, found, 5000,
                                                       f"📄 Downloading .{ext}", last_edit)

            with open(os.path.join(base, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)

            if found == 0:
                await status.edit(content=f"No .{ext} files found in this channel.")
            else:
                await status.edit(
                    content=(f"✅ .{ext} dump complete.\n"
                             f"Found: {found}\nDownloaded: {downloaded}\n"
                             f"Failed: {failed}\nSaved to `{base}`")
                )
        except (discord.Forbidden, discord.HTTPException) as e:
            try:
                await status.edit(content=f"❌ Dump failed: {e}")
            except Exception:
                pass
        except OSError:
            try:
                await status.edit(content="❌ Disk full or write error.")
            except Exception:
                pass
        except Exception as e:
            print(traceback.format_exc())
            try:
                await status.edit(content=f"❌ Dump failed: {e}")
            except Exception:
                pass
        finally:
            self._active_dumps.discard(target.id)

    # ------------------------------------------------------------------ #
    # 8. dumpcontenttype
    # ------------------------------------------------------------------ #
    @commands.command(name="dumpcontenttype")
    async def dumpcontenttype(self, ctx: commands.Context, content_type: str, channel: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        target = await self._resolve_channel(ctx, channel)
        if target is None:
            await self._safe_send(ctx, "❌ Channel not found.")
            return
        if target.id in self._active_dumps:
            await self._safe_send(ctx, "A dump is already in progress for this channel. Wait for it to complete.")
            return
        ctype_query = content_type.lower()
        sane = self._sanitize_filename(content_type).replace(" ", "_")

        status = await self._safe_send(ctx, f"🔍 Scanning {content_type}...")
        if status is None:
            return
        self._active_dumps.add(target.id)
        try:
            async with self.dump_lock:
                base = self._create_dump_dir(
                    self._guild_sub(target.guild),
                    self._channel_sub(target),
                    f"{sane}_{self._timestamp()}",
                )
            downloaded = 0
            failed = 0
            found = 0
            seen_ids: Set[int] = set()
            manifest: List[dict] = []
            last_edit = [0.0]

            async for msg in target.history(limit=None):
                if found >= 5000:
                    break
                for att in msg.attachments:
                    if found >= 5000:
                        break
                    att_ct = (getattr(att, "content_type", None) or "").lower()
                    if ctype_query not in att_ct:
                        continue
                    found += 1
                    if att.id in seen_ids:
                        continue
                    seen_ids.add(att.id)
                    ext = self._ext_for_url(att.filename, att.content_type)
                    dl_name = f"{msg.id}_{self._sanitize_filename(att.filename) or att.id}{ext}"
                    if not os.path.splitext(dl_name)[1] and ext:
                        dl_name = f"{msg.id}_{att.id}{ext}"
                    filepath = os.path.join(base, dl_name)
                    ok = await self._download_file(att.url, filepath)
                    await asyncio.sleep(0.1)
                    if ok:
                        downloaded += 1
                        manifest.append({
                            "filename": dl_name,
                            "original_url": att.url,
                            "message_id": str(msg.id),
                            "author": msg.author.name,
                            "author_id": str(msg.author.id),
                            "size": att.size,
                            "content_type": getattr(att, "content_type", None),
                        })
                    else:
                        failed += 1
                    if found % 50 == 0:
                        await self._throttled_progress(status, found, 5000,
                                                       f"📄 Downloading {content_type}", last_edit)

            with open(os.path.join(base, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)

            if found == 0:
                await status.edit(content=f"No files with content type '{content_type}' found.")
            else:
                await status.edit(
                    content=(f"✅ Content-type '{content_type}' dump complete.\n"
                             f"Found: {found}\nDownloaded: {downloaded}\n"
                             f"Failed: {failed}\nSaved to `{base}`")
                )
        except (discord.Forbidden, discord.HTTPException) as e:
            try:
                await status.edit(content=f"❌ Dump failed: {e}")
            except Exception:
                pass
        except OSError:
            try:
                await status.edit(content="❌ Disk full or write error.")
            except Exception:
                pass
        except Exception as e:
            print(traceback.format_exc())
            try:
                await status.edit(content=f"❌ Dump failed: {e}")
            except Exception:
                pass
        finally:
            self._active_dumps.discard(target.id)

    # ------------------------------------------------------------------ #
    # 9. dumpemojis
    # ------------------------------------------------------------------ #
    @commands.command(name="dumpemojis")
    async def dumpemojis(self, ctx: commands.Context, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        guild = await self._resolve_guild(ctx, server)
        if guild is None:
            await self._safe_send(ctx, "❌ Server not found.")
            return

        status = await self._safe_send(ctx, "🔍 Fetching emojis...")
        if status is None:
            return
        try:
            try:
                emojis = guild.emojis
            except AttributeError:
                emojis = await guild.fetch_emojis()
            if not emojis:
                await status.edit(content="No custom emojis in this server.")
                return

            async with self.dump_lock:
                base = self._create_dump_dir(
                    self._guild_sub(guild),
                    f"emojis_{self._timestamp()}",
                )
            manifest: List[dict] = []
            downloaded = 0
            failed = 0
            last_edit = [0.0]
            for i, emoji in enumerate(emojis, 1):
                ext = "gif" if emoji.animated else "png"
                url = str(emoji.url_as(format="gif") if emoji.animated else emoji.url)
                dl_name = f"{self._sanitize_filename(emoji.name)}_{emoji.id}.{ext}"
                ok = await self._download_file(url, os.path.join(base, dl_name))
                await asyncio.sleep(0.1)
                if ok:
                    downloaded += 1
                else:
                    failed += 1
                manifest.append({
                    "name": emoji.name,
                    "id": str(emoji.id),
                    "animated": emoji.animated,
                    "url": str(emoji.url),
                    "filename": dl_name,
                })
                await self._throttled_progress(status, i, len(emojis), "😀 Downloading emojis", last_edit)

            with open(os.path.join(base, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)

            await status.edit(
                content=(f"✅ Emoji dump complete.\n"
                         f"Total: {len(emojis)}\nDownloaded: {downloaded}\n"
                         f"Failed: {failed}\nSaved to `{base}`")
            )
        except (discord.Forbidden, discord.HTTPException) as e:
            try:
                await status.edit(content=f"❌ Dump failed: {e}")
            except Exception:
                pass
        except OSError:
            try:
                await status.edit(content="❌ Disk full or write error.")
            except Exception:
                pass
        except Exception as e:
            print(traceback.format_exc())
            try:
                await status.edit(content=f"❌ Dump failed: {e}")
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # 10. dumpstickers
    # ------------------------------------------------------------------ #
    @commands.command(name="dumpstickers")
    async def dumpstickers(self, ctx: commands.Context, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        guild = await self._resolve_guild(ctx, server)
        if guild is None:
            await self._safe_send(ctx, "❌ Server not found.")
            return

        status = await self._safe_send(ctx, "🔍 Fetching stickers...")
        if status is None:
            return
        try:
            try:
                stickers = guild.stickers
            except AttributeError:
                stickers = await guild.fetch_stickers()
            if not stickers:
                await status.edit(content="No stickers in this server.")
                return

            async with self.dump_lock:
                base = self._create_dump_dir(
                    self._guild_sub(guild),
                    f"stickers_{self._timestamp()}",
                )

            manifest: List[dict] = []
            downloaded = 0
            failed = 0
            last_edit = [0.0]
            for i, sticker in enumerate(stickers, 1):
                fmt = str(getattr(sticker, "format", None))
                if "lottie" in fmt.lower() or "json" in fmt.lower():
                    ext = "json"
                    url = str(sticker.url_as(format="json")) if hasattr(sticker, "url_as") else str(sticker.url)
                else:
                    ext = "png"
                    url = str(sticker.url)
                dl_name = f"{self._sanitize_filename(sticker.name)}_{sticker.id}.{ext}"
                ok = await self._download_file(url, os.path.join(base, dl_name))
                await asyncio.sleep(0.1)
                if ok:
                    downloaded += 1
                else:
                    failed += 1
                manifest.append({
                    "name": sticker.name,
                    "id": str(sticker.id),
                    "format": fmt,
                    "description": getattr(sticker, "description", None),
                    "emoji": getattr(sticker, "emoji", None),
                    "url": url,
                    "filename": dl_name,
                })
                await self._throttled_progress(status, i, len(stickers), "💠 Downloading stickers", last_edit)

            with open(os.path.join(base, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)

            await status.edit(
                content=(f"✅ Sticker dump complete.\n"
                         f"Total: {len(stickers)}\nDownloaded: {downloaded}\n"
                         f"Failed: {failed}\nSaved to `{base}`")
            )
        except (discord.Forbidden, discord.HTTPException) as e:
            try:
                await status.edit(content=f"❌ Dump failed: {e}")
            except Exception:
                pass
        except OSError:
            try:
                await status.edit(content="❌ Disk full or write error.")
            except Exception:
                pass
        except Exception as e:
            print(traceback.format_exc())
            try:
                await status.edit(content=f"❌ Dump failed: {e}")
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # 11. dumpavatars
    # ------------------------------------------------------------------ #
    @commands.command(name="dumpavatars")
    async def dumpavatars(self, ctx: commands.Context, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        guild = await self._resolve_guild(ctx, server)
        if guild is None:
            await self._safe_send(ctx, "❌ Server not found.")
            return

        member_count = guild.member_count or len(getattr(guild, "members", []))
        warn = ""
        if member_count and member_count > 1000:
            warn = "This may take a while for large servers...\n"

        status = await self._safe_send(ctx, f"{warn}🔍 Scanning members...")
        if status is None:
            return
        try:
            async with self.dump_lock:
                base = self._create_dump_dir(
                    self._guild_sub(guild),
                    f"avatars_{self._timestamp()}",
                )

            manifest: List[dict] = []
            downloaded = 0
            failed = 0
            skipped = 0
            processed = 0
            last_edit = [0.0]

            members = guild.members
            for member in members:
                avatar = member.display_avatar
                if avatar is None or avatar.is_default():
                    skipped += 1
                    processed += 1
                    continue
                ext = "gif" if getattr(avatar, "animated", False) else "png"
                url = str(avatar.url)
                dl_name = f"{self._sanitize_filename(member.name)}_{member.id}.{ext}"
                ok = await self._download_file(url, os.path.join(base, dl_name))
                await asyncio.sleep(0.1)
                if ok:
                    downloaded += 1
                else:
                    failed += 1
                manifest.append({
                    "user_id": str(member.id),
                    "name": member.name,
                    "discriminator": getattr(member, "discriminator", None),
                    "avatar_url": url,
                    "filename": dl_name,
                })
                processed += 1
                if processed % 50 == 0:
                    await self._throttled_progress(status, processed, len(members),
                                                   "👤 Downloading avatars", last_edit)

            with open(os.path.join(base, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)

            await status.edit(
                content=(f"✅ Avatar dump complete.\n"
                         f"Members: {len(members)}\nDownloaded: {downloaded}\n"
                         f"Skipped (default): {skipped}\nFailed: {failed}\n"
                         f"Saved to `{base}`")
            )
        except (discord.Forbidden, discord.HTTPException) as e:
            try:
                await status.edit(content=f"❌ Dump failed: {e}")
            except Exception:
                pass
        except OSError:
            try:
                await status.edit(content="❌ Disk full or write error.")
            except Exception:
                pass
        except Exception as e:
            print(traceback.format_exc())
            try:
                await status.edit(content=f"❌ Dump failed: {e}")
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # 12. dumpchannels
    # ------------------------------------------------------------------ #
    @commands.command(name="dumpchannels")
    async def dumpchannels(self, ctx: commands.Context, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        guild = await self._resolve_guild(ctx, server)
        if guild is None:
            await self._safe_send(ctx, "❌ Server not found.")
            return

        status = await self._safe_send(ctx, "🔍 Exporting channels...")
        if status is None:
            return
        try:
            async with self.dump_lock:
                base = self._create_dump_dir(
                    self._guild_sub(guild),
                    f"channels_{self._timestamp()}",
                )

            categories = []
            uncategorized = []
            tree_lines: List[str] = []

            def channel_info(ch):
                return {
                    "id": str(ch.id),
                    "name": ch.name,
                    "type": str(ch.type),
                    "position": ch.position,
                    "topic": getattr(ch, "topic", None),
                    "slowmode": getattr(ch, "slowmode_delay", 0),
                    "nsfw": getattr(ch, "nsfw", False),
                }

            for cat in guild.categories:
                cat_channels = [channel_info(ch) for ch in cat.channels]
                categories.append({
                    "id": str(cat.id),
                    "name": cat.name,
                    "position": cat.position,
                    "type": "category",
                    "channels": cat_channels,
                })
                tree_lines.append(f"📁 {cat.name}")
                for ch in cat.channels:
                    icon = "🔊" if str(ch.type) == "voice" else "💬"
                    tree_lines.append(f"  {icon} #{ch.name} ({ch.id})")

            for ch in guild.channels:
                if ch.category is None:
                    info = channel_info(ch)
                    uncategorized.append(info)
                    icon = "🔊" if str(ch.type) == "voice" else "📢"
                    tree_lines.append(f"{icon} #{ch.name} ({ch.id})")

            structure = {
                "guild_id": str(guild.id),
                "guild_name": guild.name,
                "total_channels": len(guild.channels),
                "categories": categories,
                "uncategorized": uncategorized,
            }
            with open(os.path.join(base, "channels.json"), "w", encoding="utf-8") as f:
                json.dump(structure, f, ensure_ascii=False, indent=2)
            with open(os.path.join(base, "channels.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(tree_lines))

            await status.edit(
                content=(f"✅ Channel dump complete.\n"
                         f"Total channels: {len(guild.channels)}\nSaved to `{base}`")
            )
        except (discord.Forbidden, discord.HTTPException) as e:
            try:
                await status.edit(content=f"❌ Dump failed: {e}")
            except Exception:
                pass
        except OSError:
            try:
                await status.edit(content="❌ Disk full or write error.")
            except Exception:
                pass
        except Exception as e:
            print(traceback.format_exc())
            try:
                await status.edit(content=f"❌ Dump failed: {e}")
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # 13. dumpmembers
    # ------------------------------------------------------------------ #
    @commands.command(name="dumpmembers")
    async def dumpmembers(self, ctx: commands.Context, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        guild = await self._resolve_guild(ctx, server)
        if guild is None:
            await self._safe_send(ctx, "❌ Server not found.")
            return

        warn = ""
        if (guild.member_count or 0) > 5000:
            warn = "This is a large server (>5000 members); proceeding...\n"

        status = await self._safe_send(ctx, f"{warn}🔍 Exporting members...")
        if status is None:
            return
        try:
            async with self.dump_lock:
                base = self._create_dump_dir(
                    self._guild_sub(guild),
                    f"members_{self._timestamp()}",
                )

            members = guild.members
            total = len(members)
            owner_id = guild.owner_id
            member_data: List[dict] = []
            last_edit = [0.0]

            for i, member in enumerate(members, 1):
                try:
                    roles = [{"id": str(r.id), "name": r.name} for r in member.roles if not r.is_default()]
                    top_role = member.top_role
                    member_data.append({
                        "id": str(member.id),
                        "name": member.name,
                        "discriminator": getattr(member, "discriminator", None),
                        "display_name": member.display_name,
                        "joined_at": member.joined_at.isoformat() if member.joined_at else None,
                        "created_at": member.created_at.isoformat() if member.created_at else None,
                        "roles": roles,
                        "top_role": {"id": str(top_role.id), "name": top_role.name} if top_role else None,
                        "is_bot": member.bot,
                        "is_owner": member.id == owner_id,
                        "avatar_url": str(member.display_avatar.url) if member.display_avatar else None,
                        "pending": getattr(member, "pending", False),
                    })
                except Exception:
                    continue
                if i % 200 == 0:
                    await self._throttled_progress(status, i, total, "👥 Exporting members", last_edit)

            structure = {
                "guild_id": str(guild.id),
                "guild_name": guild.name,
                "total_members": len(member_data),
                "dump_date": datetime.datetime.now().isoformat(),
                "members": member_data,
            }
            with open(os.path.join(base, "members.json"), "w", encoding="utf-8") as f:
                json.dump(structure, f, ensure_ascii=False, indent=2)

            with open(os.path.join(base, "members.csv"), "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["id", "name", "discriminator", "display_name",
                                 "joined_at", "created_at", "top_role_name", "is_bot"])
                for m in member_data:
                    writer.writerow([
                        m["id"], m["name"], m["discriminator"], m["display_name"],
                        m["joined_at"], m["created_at"],
                        m["top_role"]["name"] if m["top_role"] else "",
                        m["is_bot"],
                    ])

            await status.edit(
                content=(f"✅ Member dump complete.\n"
                         f"Total members: {len(member_data)}\nSaved to `{base}`")
            )
        except (discord.Forbidden, discord.HTTPException) as e:
            try:
                await status.edit(content=f"❌ Dump failed: {e}")
            except Exception:
                pass
        except OSError:
            try:
                await status.edit(content="❌ Disk full or write error.")
            except Exception:
                pass
        except Exception as e:
            print(traceback.format_exc())
            try:
                await status.edit(content=f"❌ Dump failed: {e}")
            except Exception:
                pass


async def setup(bot):
    await bot.add_cog(DumpCommands(bot))
