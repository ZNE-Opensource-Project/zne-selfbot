import asyncio
import datetime
import io
import re
from contextlib import suppress
from typing import Optional, Union, List

import aiohttp
import discord
from discord.ext import commands

EMBED_COLOR = 0x3498DB


class AdminCommands(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot: commands.Bot = bot

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    async def _delete_invoke(self, ctx: commands.Context) -> None:
        with suppress(discord.Forbidden, discord.NotFound, discord.HTTPException):
            await ctx.message.delete()

    async def _safe_send(self, ctx: commands.Context, content: str = None,
                         embed: discord.Embed = None) -> Optional[discord.Message]:
        try:
            return await ctx.send(content=content, embed=embed)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
            print(f"[AdminCommands] send failed: {e}")
            return None

    async def _send_error(self, ctx: commands.Context, message: str) -> None:
        msg = await self._safe_send(ctx, f"❌ {message}")
        if msg is not None:
            await asyncio.sleep(5)
            with suppress(discord.Forbidden, discord.NotFound, discord.HTTPException):
                await msg.delete()

    def _parse_channel(self, ctx: commands.Context, channel_input: str) -> Optional[discord.abc.GuildChannel]:
        if not channel_input:
            return ctx.channel
        channel_input = str(channel_input).strip()
        if channel_input.startswith('<#') and channel_input.endswith('>'):
            channel_input = channel_input[2:-1]
        if channel_input.startswith('<') and channel_input.endswith('>') and ':' in channel_input:
            channel_input = channel_input[channel_input.rfind(':') + 1:-1]
        try:
            channel_id = int(channel_input)
            return self.bot.get_channel(channel_id)
        except ValueError:
            pass
        if ctx.guild:
            for ch in ctx.guild.channels:
                if ch.name.lower() == channel_input.lower():
                    return ch
        return None

    def _parse_user(self, ctx: commands.Context, user_input: str) -> Optional[Union[discord.User, discord.Member]]:
        if not user_input:
            return ctx.author
        user_input = str(user_input).strip()
        if user_input.startswith('<@') and user_input.endswith('>'):
            user_input = user_input[2:-1]
            if user_input.startswith('!'):
                user_input = user_input[1:]
        try:
            user_id = int(user_input)
            user = self.bot.get_user(user_id)
            if user:
                return user
            if ctx.guild:
                member = ctx.guild.get_member(user_id)
                if member:
                    return member
        except ValueError:
            pass
        if '#' in user_input:
            name, disc = user_input.rsplit('#', 1)
            if ctx.guild:
                for m in ctx.guild.members:
                    if m.name == name and m.discriminator == disc:
                        return m
        if ctx.guild:
            for m in ctx.guild.members:
                if m.name.lower() == user_input.lower() or (m.display_name and m.display_name.lower() == user_input.lower()):
                    return m
        return None

    def _parse_role(self, ctx: commands.Context, role_input: str) -> Optional[discord.Role]:
        if not role_input:
            return None
        role_input = str(role_input).strip()
        if role_input.startswith('<@&') and role_input.endswith('>'):
            role_input = role_input[3:-1]
        if role_input.startswith('<') and role_input.endswith('>'):
            role_input = role_input[2:-1]
        try:
            role_id = int(role_input)
            if ctx.guild:
                return ctx.guild.get_role(role_id)
        except ValueError:
            pass
        if ctx.guild:
            for r in ctx.guild.roles:
                if r.name.lower() == role_input.lower():
                    return r
        return None

    def _parse_server(self, server_input: str) -> Optional[discord.Guild]:
        if not server_input:
            return None
        try:
            guild_id = int(str(server_input).strip())
            return self.bot.get_guild(guild_id)
        except ValueError:
            return None

    def _fmt_duration(self, seconds: int) -> str:
        seconds = int(seconds)
        if seconds <= 0:
            return "permanent"
        d, rem = divmod(seconds, 86400)
        h, rem = divmod(rem, 3600)
        m, s = divmod(rem, 60)
        parts = []
        if d:
            parts.append(f"{d}d")
        if h:
            parts.append(f"{h}h")
        if m:
            parts.append(f"{m}m")
        if s:
            parts.append(f"{s}s")
        return " ".join(parts) or "0s"

    def _mask_url(self, url: str) -> str:
        if len(url) <= 25:
            return url
        return url[:20] + "..." + url[-5:]

    async def _fetch_image_bytes(self, url: str) -> Optional[bytes]:
        try:
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status == 200 and (resp.content_type or "").startswith("image"):
                        return await resp.read()
        except Exception:
            return None
        return None

    async def _get_guild(self, ctx: commands.Context, server_input: str) -> Optional[discord.Guild]:
        if server_input is None:
            return ctx.guild
        return self._parse_server(server_input)

    # ------------------------------------------------------------------ #
    # Channel commands
    # ------------------------------------------------------------------ #
    @commands.command(name="channelinfo")
    async def channelinfo(self, ctx: commands.Context, channel: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        ch = self._parse_channel(ctx, channel)
        if ch is None:
            await self._send_error(ctx, "Channel not found.")
            return
        embed = discord.Embed(title=f"# {getattr(ch, 'name', 'Unknown')}", color=EMBED_COLOR)
        embed.add_field(name="ID", value=ch.id, inline=True)
        embed.add_field(name="Type", value=str(ch.type), inline=True)
        embed.add_field(name="Position", value=getattr(ch, 'position', 'N/A'), inline=True)
        cat = getattr(ch, 'category', None)
        embed.add_field(name="Category", value=cat.name if cat else "None", inline=True)
        embed.add_field(name="Created At", value=ch.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        embed.add_field(name="NSFW", value=getattr(ch, 'nsfw', False), inline=True)
        embed.add_field(name="Slowmode", value=f"{getattr(ch, 'slowmode_delay', 0)}s", inline=True)
        if isinstance(ch, discord.TextChannel):
            embed.add_field(name="Topic", value=ch.topic or "None", inline=False)
        if isinstance(ch, (discord.VoiceChannel, discord.StageChannel)):
            embed.add_field(name="Bitrate", value=getattr(ch, 'bitrate', 'N/A'), inline=True)
            embed.add_field(name="User Limit", value=getattr(ch, 'user_limit', 0) or "Unlimited", inline=True)
        synced = getattr(ch, 'permissions_synced', None)
        embed.add_field(name="Permissions Synced", value=synced if synced is not None else "N/A", inline=True)
        await self._safe_send(ctx, embed=embed)

    @commands.command(name="textchannel")
    async def textchannel(self, ctx: commands.Context, *, name: str) -> None:
        await self._delete_invoke(ctx)
        if ctx.guild is None:
            await self._send_error(ctx, "This command requires a server.")
            return
        clean = name.lower().replace(" ", "-")
        ch = await ctx.guild.create_text_channel(name=clean)
        await self._safe_send(ctx, f"Created text channel `#{ch.name}` ({ch.id})")

    @commands.command(name="voicechannel")
    async def voicechannel(self, ctx: commands.Context, *, name: str) -> None:
        await self._delete_invoke(ctx)
        if ctx.guild is None:
            await self._send_error(ctx, "This command requires a server.")
            return
        clean = name.lower().replace(" ", "-")
        ch = await ctx.guild.create_voice_channel(name=clean)
        await self._safe_send(ctx, f"Created voice channel `{ch.name}` ({ch.id})")

    @commands.command(name="stagechannel")
    async def stagechannel(self, ctx: commands.Context, *, name: str) -> None:
        await self._delete_invoke(ctx)
        if ctx.guild is None:
            await self._send_error(ctx, "This command requires a server.")
            return
        clean = name.lower().replace(" ", "-")
        ch = await ctx.guild.create_stage_channel(name=clean)
        await self._safe_send(ctx, f"Created stage channel `{ch.name}` ({ch.id})")

    @commands.command(name="newschannel")
    async def newschannel(self, ctx: commands.Context, *, name: str) -> None:
        await self._delete_invoke(ctx)
        if ctx.guild is None:
            await self._send_error(ctx, "This command requires a server.")
            return
        clean = name.lower().replace(" ", "-")
        if not ctx.guild.features or "NEWS" not in ctx.guild.features and not hasattr(discord.ChannelType, "news"):
            pass
        try:
            ch = await ctx.guild.create_text_channel(name=clean, type=discord.ChannelType.news)
            await self._safe_send(ctx, f"Created news channel `#{ch.name}` ({ch.id})")
        except discord.HTTPException as e:
            await self._send_error(ctx, f"News channels not supported here: {e.text}")

    @commands.command(name="thread")
    async def thread(self, ctx: commands.Context, *, name: str) -> None:
        await self._delete_invoke(ctx)
        if not isinstance(ctx.channel, discord.TextChannel):
            await self._send_error(ctx, "Threads can only be created in text channels.")
            return
        th = await ctx.channel.create_thread(name=name, type=discord.ChannelType.public_thread, auto_archive_duration=1440)
        await self._safe_send(ctx, f"Created thread {th.mention} ({th.id})")

    @commands.command(name="category")
    async def category(self, ctx: commands.Context, *, name: str) -> None:
        await self._delete_invoke(ctx)
        if ctx.guild is None:
            await self._send_error(ctx, "This command requires a server.")
            return
        cat = await ctx.guild.create_category(name=name)
        await self._safe_send(ctx, f"Created category `{cat.name}` ({cat.id})")

    @commands.command(name="deletecategory")
    async def deletecategory(self, ctx: commands.Context, category_id: str) -> None:
        await self._delete_invoke(ctx)
        try:
            cid = int(category_id.strip())
        except ValueError:
            await self._send_error(ctx, "Invalid category ID.")
            return
        if ctx.guild is None:
            await self._send_error(ctx, "This command requires a server.")
            return
        cat = ctx.guild.get_channel(cid)
        if cat is None or not isinstance(cat, discord.CategoryChannel):
            await self._send_error(ctx, "Category not found.")
            return
        for ch in cat.channels:
            with suppress(discord.HTTPException, discord.Forbidden):
                await ch.delete()
        await cat.delete()
        await self._safe_send(ctx, "Deleted category and all channels.")

    @commands.command(name="renamechannel")
    async def renamechannel(self, ctx: commands.Context, channel: str, *, name: str) -> None:
        await self._delete_invoke(ctx)
        ch = self._parse_channel(ctx, channel)
        if ch is None:
            await self._send_error(ctx, "Channel not found.")
            return
        await ch.edit(name=name)
        await self._safe_send(ctx, f"Renamed channel to `{name}`.")

    @commands.command(name="deletechannel")
    async def deletechannel(self, ctx: commands.Context, channel: str) -> None:
        await self._delete_invoke(ctx)
        ch = self._parse_channel(ctx, channel)
        if ch is None:
            await self._send_error(ctx, "Channel not found.")
            return
        await ch.delete()
        await self._safe_send(ctx, f"Deleted channel `{getattr(ch, 'name', ch.id)}`.")

    @commands.command(name="slowmode")
    async def slowmode(self, ctx: commands.Context, channel: str, seconds: int) -> None:
        await self._delete_invoke(ctx)
        ch = self._parse_channel(ctx, channel)
        if ch is None:
            await self._send_error(ctx, "Channel not found.")
            return
        seconds = max(0, min(21600, seconds))
        await ch.edit(slowmode_delay=seconds)
        await self._safe_send(ctx, f"Set slowmode to {seconds}s in `{getattr(ch, 'name', ch.id)}`.")

    @commands.command(name="removeslowmode")
    async def removeslowmode(self, ctx: commands.Context, channel: str) -> None:
        await self._delete_invoke(ctx)
        ch = self._parse_channel(ctx, channel)
        if ch is None:
            await self._send_error(ctx, "Channel not found.")
            return
        await ch.edit(slowmode_delay=0)
        await self._safe_send(ctx, f"Removed slowmode in `{getattr(ch, 'name', ch.id)}`.")

    @commands.command(name="lockchannel")
    async def lockchannel(self, ctx: commands.Context, channel: str) -> None:
        await self._delete_invoke(ctx)
        ch = self._parse_channel(ctx, channel)
        if ch is None:
            await self._send_error(ctx, "Channel not found.")
            return
        if ctx.guild is None:
            await self._send_error(ctx, "This command requires a server.")
            return
        overwrite = ch.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await self._safe_send(ctx, f"Locked `{getattr(ch, 'name', ch.id)}`.")

    @commands.command(name="unlockchannel")
    async def unlockchannel(self, ctx: commands.Context, channel: str) -> None:
        await self._delete_invoke(ctx)
        ch = self._parse_channel(ctx, channel)
        if ch is None:
            await self._send_error(ctx, "Channel not found.")
            return
        if ctx.guild is None:
            await self._send_error(ctx, "This command requires a server.")
            return
        overwrite = ch.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await self._safe_send(ctx, f"Unlocked `{getattr(ch, 'name', ch.id)}`.")

    # ------------------------------------------------------------------ #
    # Purge commands
    # ------------------------------------------------------------------ #
    async def _purge_generic(self, ctx, amount, delay, channel, check):
        amount = max(1, min(1000, int(amount)))
        if delay and delay > 0:
            deleted = 0
            async for msg in channel.history(limit=amount):
                if check(msg):
                    with suppress(discord.HTTPException, discord.Forbidden):
                        await msg.delete()
                        deleted += 1
                    await asyncio.sleep(delay)
            return deleted
        return await channel.purge(limit=amount, check=check)

    @commands.command(name="purge")
    async def purge(self, ctx: commands.Context, amount: int, delay: Optional[float] = None,
                    channel: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        ch = self._parse_channel(ctx, channel) if channel else ctx.channel
        if ch is None:
            await self._send_error(ctx, "Channel not found.")
            return
        count = await self._purge_generic(ctx, amount, delay, ch, lambda m: True)
        count = count if isinstance(count, int) else len(count)
        msg = await self._safe_send(ctx, f"🧹 Purged {count} message(s).")
        if msg is not None:
            await asyncio.sleep(3)
            with suppress(discord.HTTPException, discord.Forbidden):
                await msg.delete()

    @commands.command(name="purgeself")
    async def purgeself(self, ctx: commands.Context, amount: int, delay: Optional[float] = None,
                        channel: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        ch = self._parse_channel(ctx, channel) if channel else ctx.channel
        if ch is None:
            await self._send_error(ctx, "Channel not found.")
            return
        count = await self._purge_generic(ctx, amount, delay, ch, lambda m: m.author.id == ctx.author.id)
        count = count if isinstance(count, int) else len(count)
        msg = await self._safe_send(ctx, f"🧹 Purged {count} of your message(s).")
        if msg is not None:
            await asyncio.sleep(3)
            with suppress(discord.HTTPException, discord.Forbidden):
                await msg.delete()

    @commands.command(name="purgeuser")
    async def purgeuser(self, ctx: commands.Context, amount: int, user: str, delay: Optional[float] = None,
                        channel: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        target = self._parse_user(ctx, user)
        if target is None:
            await self._send_error(ctx, "User not found.")
            return
        ch = self._parse_channel(ctx, channel) if channel else ctx.channel
        if ch is None:
            await self._send_error(ctx, "Channel not found.")
            return
        count = await self._purge_generic(ctx, amount, delay, ch, lambda m: m.author.id == target.id)
        count = count if isinstance(count, int) else len(count)
        msg = await self._safe_send(ctx, f"🧹 Purged {count} message(s) from {target}.")
        if msg is not None:
            await asyncio.sleep(3)
            with suppress(discord.HTTPException, discord.Forbidden):
                await msg.delete()

    def _extract_message_id(self, value: str) -> Optional[int]:
        value = value.strip()
        m = re.search(r"discord(?:app)?\.com/channels/\d+/\d+/(\d+)", value)
        if m:
            return int(m.group(1))
        value = value.strip("< >")
        try:
            return int(value)
        except ValueError:
            return None

    @commands.command(name="purgerange")
    async def purgerange(self, ctx: commands.Context, start: str, end: str, delay: Optional[float] = None,
                         channel: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        ch = self._parse_channel(ctx, channel) if channel else ctx.channel
        if ch is None:
            await self._send_error(ctx, "Channel not found.")
            return
        start_id = self._extract_message_id(start)
        end_id = self._extract_message_id(end)
        if not start_id or not end_id:
            await self._send_error(ctx, "Invalid message ID/link.")
            return
        if start_id > end_id:
            start_id, end_id = end_id, start_id
        start_msg = await ch.fetch_message(start_id)
        end_msg = await ch.fetch_message(end_id)
        if delay and delay > 0:
            async for msg in ch.history(limit=None, after=start_msg, before=end_msg):
                with suppress(discord.HTTPException, discord.Forbidden):
                    await msg.delete()
                    await asyncio.sleep(delay)
            for edge in (start_msg, end_msg):
                with suppress(discord.HTTPException, discord.Forbidden):
                    await edge.delete()
            count = "range"
        else:
            await ch.purge(after=start_msg.created_at, before=end_msg.created_at, limit=None)
            for edge in (start_msg, end_msg):
                with suppress(discord.HTTPException, discord.Forbidden):
                    await edge.delete()
            count = "range"
        msg = await self._safe_send(ctx, f"🧹 Purged messages in the given range.")
        if msg is not None:
            await asyncio.sleep(3)
            with suppress(discord.HTTPException, discord.Forbidden):
                await msg.delete()

    @commands.command(name="nuke")
    async def nuke(self, ctx: commands.Context, channel: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        ch = self._parse_channel(ctx, channel) if channel else ctx.channel
        if ch is None:
            await self._send_error(ctx, "Channel not found.")
            return
        try:
            new_ch = await ch.clone()
            await ch.delete()
            nmsg = await self._safe_send(new_ch, "☢️ Channel nuked.")
            if nmsg is not None:
                await asyncio.sleep(2)
                with suppress(discord.HTTPException, discord.Forbidden):
                    await nmsg.delete()
        except (discord.Forbidden, discord.HTTPException):
            async for msg in ch.history(limit=None):
                with suppress(discord.HTTPException, discord.Forbidden):
                    await msg.delete()

    @commands.command(name="ackchannel")
    async def ackchannel(self, ctx: commands.Context, channel: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        ch = self._parse_channel(ctx, channel) if channel else ctx.channel
        if ch is None:
            await self._send_error(ctx, "Channel not found.")
            return
        try:
            last = await ch.history(limit=1).flatten()
            if last:
                await self.bot.http.ack_message(ch.id, last[0].id)
        except Exception:
            pass

    @commands.command(name="ackmessage")
    async def ackmessage(self, ctx: commands.Context, channel: str, message_id: int) -> None:
        await self._delete_invoke(ctx)
        ch = self._parse_channel(ctx, channel)
        if ch is None:
            await self._send_error(ctx, "Channel not found.")
            return
        try:
            await self.bot.http.ack_message(ch.id, message_id)
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Webhook commands
    # ------------------------------------------------------------------ #
    @commands.command(name="listwebhooks")
    async def listwebhooks(self, ctx: commands.Context, channel: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        ch = self._parse_channel(ctx, channel) if channel else ctx.channel
        if ch is None:
            await self._send_error(ctx, "Channel not found.")
            return
        if not isinstance(ch, discord.TextChannel):
            await self._send_error(ctx, "Webhooks require a text channel.")
            return
        webhooks = await ch.webhooks()
        if not webhooks:
            await self._safe_send(ctx, "No webhooks in this channel.")
            return
        lines = []
        for wh in webhooks:
            lines.append(f"{wh.name} | ID: {wh.id} | URL: {self._mask_url(wh.url)}")
        await self._safe_send(ctx, "```\n" + "\n".join(lines) + "\n```")

    @commands.command(name="createwebhook")
    async def createwebhook(self, ctx: commands.Context, channel: Optional[str] = None, *, name: str = "ZNE Webhook") -> None:
        await self._delete_invoke(ctx)
        ch = self._parse_channel(ctx, channel) if channel else ctx.channel
        if ch is None:
            await self._send_error(ctx, "Channel not found.")
            return
        if not isinstance(ch, discord.TextChannel):
            await self._send_error(ctx, "Webhooks require a text channel.")
            return
        wh = await ch.create_webhook(name=name)
        await self._safe_send(ctx, f"```\nName: {wh.name}\nID: {wh.id}\nURL: {wh.url}\n```")

    def _parse_webhook_url(self, url: str):
        m = re.search(r"discord(?:app)?\.com/api(?:/v\d+)?/webhooks/(\d+)/([\w-]+)", url)
        if not m:
            return None, None
        return int(m.group(1)), m.group(2)

    @commands.command(name="webhookinfo")
    async def webhookinfo(self, ctx: commands.Context, *, url: str) -> None:
        await self._delete_invoke(ctx)
        wh_id, token = self._parse_webhook_url(url)
        if wh_id is None:
            await self._send_error(ctx, "Invalid webhook URL.")
            return
        wh = await self.bot.fetch_webhook(wh_id, token=token)
        embed = discord.Embed(title=f"Webhook: {wh.name}", color=EMBED_COLOR)
        embed.add_field(name="ID", value=wh.id, inline=True)
        embed.add_field(name="Channel", value=f"{wh.channel} ({wh.channel_id})" if wh.channel else wh.channel_id, inline=True)
        embed.add_field(name="Guild", value=wh.guild_id, inline=True)
        embed.add_field(name="Token", value="hidden", inline=True)
        if wh.avatar:
            embed.set_thumbnail(url=wh.avatar.url)
        await self._safe_send(ctx, embed=embed)

    @commands.command(name="webhooksend")
    async def webhooksend(self, ctx: commands.Context, url: str, *, message: str) -> None:
        await self._delete_invoke(ctx)
        wh_id, token = self._parse_webhook_url(url)
        if wh_id is None:
            await self._send_error(ctx, "Invalid webhook URL.")
            return
        wh = discord.Webhook.from_url(url, session=self.bot.http._HTTPClient__session)
        await wh.send(content=message, wait=True)
        await self._safe_send(ctx, "✅ Message sent via webhook.")

    @commands.command(name="webhookdelete")
    async def webhookdelete(self, ctx: commands.Context, *, url: str) -> None:
        await self._delete_invoke(ctx)
        wh_id, token = self._parse_webhook_url(url)
        if wh_id is None:
            await self._send_error(ctx, "Invalid webhook URL.")
            return
        wh = await self.bot.fetch_webhook(wh_id, token=token)
        await wh.delete()
        await self._safe_send(ctx, "✅ Webhook deleted.")

    # ------------------------------------------------------------------ #
    # User commands
    # ------------------------------------------------------------------ #
    @commands.command(name="userinfo")
    async def userinfo(self, ctx: commands.Context, user: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        target = self._parse_user(ctx, user) if user else ctx.author
        if target is None:
            await self._send_error(ctx, "User not found.")
            return
        embed = discord.Embed(title=f"{target} ({target.id})", color=getattr(target, 'colour', EMBED_COLOR) or EMBED_COLOR)
        embed.add_field(name="Username", value=f"{target.name}#{target.discriminator}", inline=True)
        embed.add_field(name="Display Name", value=getattr(target, 'display_name', target.name), inline=True)
        embed.add_field(name="Created At", value=target.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        if isinstance(target, discord.Member):
            embed.add_field(name="Joined At", value=target.joined_at.strftime("%Y-%m-%d %H:%M:%S") if target.joined_at else "N/A", inline=True)
            roles = [r.name for r in target.roles if not r.is_default()]
            embed.add_field(name="Roles", value=", ".join(roles) if roles else "None", inline=False)
            embed.add_field(name="Top Role", value=target.top_role.name if target.top_role else "None", inline=True)
        embed.add_field(name="Bot", value=target.bot, inline=True)
        embed.add_field(name="System", value=getattr(target, 'system', False), inline=True)
        with suppress(Exception):
            embed.add_field(name="Status", value=str(target.raw_status), inline=True)
        if target.avatar:
            embed.set_thumbnail(url=target.avatar.url)
        if getattr(target, 'banner', None):
            embed.set_image(url=target.banner.url)
        await self._safe_send(ctx, embed=embed)

    @commands.command(name="userage")
    async def userage(self, ctx: commands.Context, user: str) -> None:
        await self._delete_invoke(ctx)
        target = self._parse_user(ctx, user)
        if target is None:
            await self._send_error(ctx, "User not found.")
            return
        delta = discord.utils.utcnow() - target.created_at
        days, rem = divmod(delta.total_seconds(), 86400)
        hours, rem = divmod(rem, 3600)
        minutes = rem // 60
        await self._safe_send(ctx, f"Account created {target.created_at.strftime('%Y-%m-%d %H:%M:%S')}. "
                                    f"Age: {int(days)} days, {int(hours)} hours, {int(minutes)} minutes")

    @commands.command(name="mutualfriends")
    async def mutualfriends(self, ctx: commands.Context, user: str) -> None:
        await self._delete_invoke(ctx)
        target = self._parse_user(ctx, user)
        if target is None:
            await self._send_error(ctx, "User not found.")
            return
        try:
            data = await self.bot.http.get_mutual_friends(target.id)
            if not data:
                await self._safe_send(ctx, "No mutual friends.")
                return
            lines = [f"{u.get('username')}#{u.get('discriminator')} ({u.get('id')})" for u in data]
            await self._safe_send(ctx, "```\nMutual Friends:\n" + "\n".join(lines) + "\n```")
        except discord.HTTPException as e:
            await self._send_error(ctx, f"Mutual friends endpoint unavailable: {e.text}")

    @commands.command(name="mutualservers")
    async def mutualservers(self, ctx: commands.Context, user: str) -> None:
        await self._delete_invoke(ctx)
        target = self._parse_user(ctx, user)
        if target is None:
            await self._send_error(ctx, "User not found.")
            return
        guilds = getattr(target, 'mutual_guilds', [])
        if not guilds:
            await self._safe_send(ctx, "No mutual servers.")
            return
        lines = [f"{g.name} ({g.id})" for g in guilds]
        await self._safe_send(ctx, "```\nMutual Servers:\n" + "\n".join(lines) + "\n```")

    @commands.command(name="platform")
    async def platform(self, ctx: commands.Context, user: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        target = self._parse_user(ctx, user) if user else ctx.author
        if target is None:
            await self._send_error(ctx, "User not found.")
            return
        d = getattr(target, 'desktop_status', discord.Status.offline)
        w = getattr(target, 'web_status', discord.Status.offline)
        m = getattr(target, 'mobile_status', discord.Status.offline)
        if all(str(s) == "offline" for s in (d, w, m)):
            await self._safe_send(ctx, "User is offline on all platforms.")
            return
        await self._safe_send(ctx, f"Desktop: {d}\nWeb: {w}\nMobile: {m}")

    @commands.command(name="avatar")
    async def avatar(self, ctx: commands.Context, user: str) -> None:
        await self._delete_invoke(ctx)
        target = self._parse_user(ctx, user)
        if target is None:
            await self._send_error(ctx, "User not found.")
            return
        av = target.display_avatar or target.avatar
        if av is None:
            await self._safe_send(ctx, "User has no avatar.")
            return
        embed = discord.Embed(title=f"{target}'s avatar", color=EMBED_COLOR)
        embed.set_image(url=av.url)
        await self._safe_send(ctx, embed=embed)

    @commands.command(name="banner")
    async def banner(self, ctx: commands.Context, user: str) -> None:
        await self._delete_invoke(ctx)
        target = self._parse_user(ctx, user)
        if target is None:
            await self._send_error(ctx, "User not found.")
            return
        try:
            fetched = await self.bot.fetch_user(target.id)
        except discord.HTTPException:
            fetched = target
        if getattr(fetched, 'banner', None) is None:
            await self._safe_send(ctx, "User has no banner.")
            return
        embed = discord.Embed(title=f"{target}'s banner", color=EMBED_COLOR)
        embed.set_image(url=fetched.banner.url)
        await self._safe_send(ctx, embed=embed)

    @commands.command(name="report")
    async def report(self, ctx: commands.Context, message_link: str, *, reason: str) -> None:
        await self._delete_invoke(ctx)
        m = re.search(r"discord(?:app)?\.com/channels/(\d+)/(\d+)/(\d+)", message_link)
        if not m:
            await self._send_error(ctx, "Invalid message link.")
            return
        guild_id, channel_id, message_id = int(m.group(1)), int(m.group(2)), int(m.group(3))
        ch = self.bot.get_channel(channel_id)
        if ch is None:
            await self._send_error(ctx, "Channel not found.")
            return
        msg = await ch.fetch_message(message_id)
        author = msg.author
        print(f"[REPORT] Message {message_id} by {author} ({author.id}) in guild {guild_id} reported for: {reason}")
        await self._safe_send(ctx, f"🚩 Message by {author} reported for: {reason}")

    # ------------------------------------------------------------------ #
    # Moderation commands
    # ------------------------------------------------------------------ #
    async def _ensure_muted_role(self, guild: discord.Guild) -> discord.Role:
        role = discord.utils.get(guild.roles, name="Muted")
        if role is None:
            role = await guild.create_role(name="Muted", permissions=discord.Permissions.none())
            for ch in guild.text_channels:
                with suppress(discord.HTTPException, discord.Forbidden):
                    await ch.set_permissions(role, send_messages=False)
        return role

    @commands.command(name="mute")
    async def mute(self, ctx: commands.Context, user: str) -> None:
        await self._delete_invoke(ctx)
        target = self._parse_user(ctx, user)
        if target is None or not isinstance(target, discord.Member):
            await self._send_error(ctx, "User not found in this server.")
            return
        role = await self._ensure_muted_role(ctx.guild)
        await target.add_roles(role, reason="Muted")
        with suppress(Exception):
            await target.timeout(datetime.timedelta(minutes=40320), reason="Muted")
        await self._safe_send(ctx, f"🔇 Muted {target}.")

    @commands.command(name="unmute")
    async def unmute(self, ctx: commands.Context, user: str) -> None:
        await self._delete_invoke(ctx)
        target = self._parse_user(ctx, user)
        if target is None or not isinstance(target, discord.Member):
            await self._send_error(ctx, "User not found in this server.")
            return
        role = discord.utils.get(ctx.guild.roles, name="Muted")
        if role:
            await target.remove_roles(role, reason="Unmuted")
        with suppress(Exception):
            await target.timeout(None)
        await self._safe_send(ctx, f"🔊 Unmuted {target}.")

    @commands.command(name="timeout")
    async def timeout(self, ctx: commands.Context, user: str, seconds: int) -> None:
        await self._delete_invoke(ctx)
        target = self._parse_user(ctx, user)
        if target is None or not isinstance(target, discord.Member):
            await self._send_error(ctx, "User not found in this server.")
            return
        seconds = max(1, min(2419200, seconds))
        await target.timeout(datetime.timedelta(seconds=seconds), reason="Timeout command")
        await self._safe_send(ctx, f"⏱️ Timed out {target} for {self._fmt_duration(seconds)}.")

    @commands.command(name="removetimeout")
    async def removetimeout(self, ctx: commands.Context, user: str) -> None:
        await self._delete_invoke(ctx)
        target = self._parse_user(ctx, user)
        if target is None or not isinstance(target, discord.Member):
            await self._send_error(ctx, "User not found in this server.")
            return
        await target.timeout(None)
        await self._safe_send(ctx, f"✅ Removed timeout from {target}.")

    @commands.command(name="kick")
    async def kick(self, ctx: commands.Context, user: str, *, reason: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        target = self._parse_user(ctx, user)
        if target is None or not isinstance(target, discord.Member):
            await self._send_error(ctx, "User not found in this server.")
            return
        await target.kick(reason=reason)
        await self._safe_send(ctx, f"👢 Kicked {target}." + (f" Reason: {reason}" if reason else ""))

    @commands.command(name="ban")
    async def ban(self, ctx: commands.Context, user: str, *, reason: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        target = self._parse_user(ctx, user)
        if target is None or not isinstance(target, discord.Member):
            await self._send_error(ctx, "User not found in this server.")
            return
        await target.ban(reason=reason, delete_message_days=0)
        await self._safe_send(ctx, f"🔨 Banned {target}." + (f" Reason: {reason}" if reason else ""))

    @commands.command(name="hackban")
    async def hackban(self, ctx: commands.Context, user_id: int, *, reason: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        if ctx.guild is None:
            await self._send_error(ctx, "This command requires a server.")
            return
        await ctx.guild.ban(discord.Object(id=user_id), reason=reason)
        await self._safe_send(ctx, f"🔨 Hackbanned {user_id}." + (f" Reason: {reason}" if reason else ""))

    @commands.command(name="softban")
    async def softban(self, ctx: commands.Context, user: str, *, reason: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        target = self._parse_user(ctx, user)
        if target is None or not isinstance(target, discord.Member):
            await self._send_error(ctx, "User not found in this server.")
            return
        await target.ban(reason=reason or "Softban", delete_message_days=7)
        await ctx.guild.unban(target, reason="Softban")
        await self._safe_send(ctx, f"♻️ Softbanned {target}.")

    @commands.command(name="unban")
    async def unban(self, ctx: commands.Context, user_id: int) -> None:
        await self._delete_invoke(ctx)
        if ctx.guild is None:
            await self._send_error(ctx, "This command requires a server.")
            return
        await ctx.guild.unban(discord.Object(id=user_id))
        await self._safe_send(ctx, f"✅ Unbanned {user_id}.")

    @commands.command(name="banlist")
    async def banlist(self, ctx: commands.Context, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        guild = await self._get_guild(ctx, server)
        if guild is None:
            await self._send_error(ctx, "Server not found.")
            return
        bans = await guild.bans(limit=None)
        if not bans:
            await self._safe_send(ctx, "No banned users.")
            return
        lines = []
        for i, b in enumerate(bans, 1):
            u = b.user
            lines.append(f"{i}. {u.name}#{u.discriminator} ({u.id}) - {b.reason or 'No reason'}")
        pages = [lines[i:i + 20] for i in range(0, len(lines), 20)]
        for p in pages:
            await self._safe_send(ctx, "```\n" + "\n".join(p) + "\n```")

    @commands.command(name="copybans")
    async def copybans(self, ctx: commands.Context, source: str, dest: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        src = self._parse_server(source)
        dst = self._parse_server(dest) if dest else ctx.guild
        if src is None or dst is None:
            await self._send_error(ctx, "Server not found.")
            return
        src_bans = await src.bans(limit=None)
        existing = {b.user.id for b in await dst.bans(limit=None)}
        copied = failed = already = 0
        for b in src_bans:
            if b.user.id in existing:
                already += 1
                continue
            try:
                await dst.ban(discord.Object(id=b.user.id), reason="Copied ban")
                copied += 1
            except discord.HTTPException:
                failed += 1
        await self._safe_send(ctx, f"Copied {copied} bans. {already} already banned. {failed} failed.")

    # ------------------------------------------------------------------ #
    # Nickname commands
    # ------------------------------------------------------------------ #
    @commands.command(name="nick")
    async def nick(self, ctx: commands.Context, *, text: str) -> None:
        await self._delete_invoke(ctx)
        if ctx.guild is None:
            await self._send_error(ctx, "This command requires a server.")
            return
        value = None if text.lower() in ("none", "clear") else text
        await ctx.guild.me.edit(nick=value)
        await self._safe_send(ctx, "✅ Nickname updated." if value else "✅ Nickname cleared.")

    @commands.command(name="nickuser")
    async def nickuser(self, ctx: commands.Context, user: str, *, text: str) -> None:
        await self._delete_invoke(ctx)
        target = self._parse_user(ctx, user)
        if target is None or not isinstance(target, discord.Member):
            await self._send_error(ctx, "User not found in this server.")
            return
        await target.edit(nick=text)
        await self._safe_send(ctx, f"✅ Changed nickname for {target}.")

    @commands.command(name="clearnick")
    async def clearnick(self, ctx: commands.Context, user: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        if user:
            target = self._parse_user(ctx, user)
        else:
            target = ctx.guild.me if ctx.guild else None
        if target is None or not isinstance(target, discord.Member):
            await self._send_error(ctx, "User not found in this server.")
            return
        await target.edit(nick=None)
        await self._safe_send(ctx, f"✅ Cleared nickname for {target}.")

    # ------------------------------------------------------------------ #
    # Server commands
    # ------------------------------------------------------------------ #
    @commands.command(name="serverinfo")
    async def serverinfo(self, ctx: commands.Context, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        guild = await self._get_guild(ctx, server)
        if guild is None:
            await self._send_error(ctx, "Server not found.")
            return
        embed = discord.Embed(title=guild.name, color=EMBED_COLOR)
        embed.add_field(name="ID", value=guild.id, inline=True)
        embed.add_field(name="Owner", value=f"{guild.owner} ({guild.owner_id})" if guild.owner else guild.owner_id, inline=True)
        embed.add_field(name="Created At", value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        embed.add_field(name="Members", value=guild.member_count, inline=True)
        embed.add_field(name="Channels", value=len(guild.channels), inline=True)
        embed.add_field(name="Roles", value=len(guild.roles), inline=True)
        embed.add_field(name="Boost Level", value=guild.premium_tier, inline=True)
        embed.add_field(name="Boosters", value=len(guild.premium_subscribers), inline=True)
        embed.add_field(name="Verification", value=str(guild.verification_level), inline=True)
        embed.add_field(name="Content Filter", value=str(guild.explicit_content_filter), inline=True)
        embed.add_field(name="Locale", value=guild.preferred_locale, inline=True)
        if guild.features:
            embed.add_field(name="Features", value=", ".join(guild.features[:15]), inline=False)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        if guild.banner:
            embed.set_image(url=guild.banner.url)
        await self._safe_send(ctx, embed=embed)

    @commands.command(name="serverage")
    async def serverage(self, ctx: commands.Context, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        guild = await self._get_guild(ctx, server)
        if guild is None:
            await self._send_error(ctx, "Server not found.")
            return
        delta = discord.utils.utcnow() - guild.created_at
        days, rem = divmod(delta.total_seconds(), 86400)
        hours, rem = divmod(rem, 3600)
        minutes = rem // 60
        await self._safe_send(ctx, f"Server created {guild.created_at.strftime('%Y-%m-%d %H:%M:%S')}. "
                                    f"Age: {int(days)} days, {int(hours)} hours, {int(minutes)} minutes")

    @commands.command(name="serverowner")
    async def serverowner(self, ctx: commands.Context, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        guild = await self._get_guild(ctx, server)
        if guild is None:
            await self._send_error(ctx, "Server not found.")
            return
        owner = guild.owner or await guild.fetch_owner()
        await self._safe_send(ctx, f"Owner: {owner} ({owner.id})")

    @commands.command(name="servericon")
    async def servericon(self, ctx: commands.Context, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        guild = await self._get_guild(ctx, server)
        if guild is None:
            await self._send_error(ctx, "Server not found.")
            return
        if guild.icon is None:
            await self._safe_send(ctx, "Server has no icon.")
            return
        embed = discord.Embed(title=f"{guild.name} icon", color=EMBED_COLOR)
        embed.set_image(url=guild.icon.url)
        await self._safe_send(ctx, embed=embed)

    @commands.command(name="serverbanner")
    async def serverbanner(self, ctx: commands.Context, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        guild = await self._get_guild(ctx, server)
        if guild is None:
            await self._send_error(ctx, "Server not found.")
            return
        if guild.banner is None:
            await self._safe_send(ctx, "Server has no banner.")
            return
        embed = discord.Embed(title=f"{guild.name} banner", color=EMBED_COLOR)
        embed.set_image(url=guild.banner.url)
        await self._safe_send(ctx, embed=embed)

    @commands.command(name="serversplash")
    async def serversplash(self, ctx: commands.Context, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        guild = await self._get_guild(ctx, server)
        if guild is None:
            await self._send_error(ctx, "Server not found.")
            return
        if guild.splash is None:
            await self._safe_send(ctx, "Server has no invite splash.")
            return
        embed = discord.Embed(title=f"{guild.name} splash", color=EMBED_COLOR)
        embed.set_image(url=guild.splash.url)
        await self._safe_send(ctx, embed=embed)

    @commands.command(name="serverdsplash")
    async def serverdsplash(self, ctx: commands.Context, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        guild = await self._get_guild(ctx, server)
        if guild is None:
            await self._send_error(ctx, "Server not found.")
            return
        if guild.discovery_splash is None:
            await self._safe_send(ctx, "Server has no discovery splash.")
            return
        embed = discord.Embed(title=f"{guild.name} discovery splash", color=EMBED_COLOR)
        embed.set_image(url=guild.discovery_splash.url)
        await self._safe_send(ctx, embed=embed)

    @commands.command(name="serverboosters")
    async def serverboosters(self, ctx: commands.Context, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        guild = await self._get_guild(ctx, server)
        if guild is None:
            await self._send_error(ctx, "Server not found.")
            return
        boosters = guild.premium_subscribers
        if not boosters:
            await self._safe_send(ctx, "No boosters.")
            return
        lines = [f"{b.name} ({b.id})" for b in boosters]
        await self._safe_send(ctx, "```\nBoosters:\n" + "\n".join(lines) + "\n```")

    @commands.command(name="serverboostlevel")
    async def serverboostlevel(self, ctx: commands.Context, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        guild = await self._get_guild(ctx, server)
        if guild is None:
            await self._send_error(ctx, "Server not found.")
            return
        emojis = {0: "⚪", 1: "🟢", 2: "🔵", 3: "🟣"}
        await self._safe_send(ctx, f"Boost level: {emojis.get(guild.premium_tier, '⚪')} Tier {guild.premium_tier}")

    @commands.command(name="setservername")
    async def setservername(self, ctx: commands.Context, *, name: str) -> None:
        await self._delete_invoke(ctx)
        if ctx.guild is None:
            await self._send_error(ctx, "This command requires a server.")
            return
        await ctx.guild.edit(name=name)
        await self._safe_send(ctx, f"✅ Server renamed to `{name}`.")

    @commands.command(name="setservericon")
    async def setservericon(self, ctx: commands.Context, url: str) -> None:
        await self._delete_invoke(ctx)
        if ctx.guild is None:
            await self._send_error(ctx, "This command requires a server.")
            return
        data = await self._fetch_image_bytes(url)
        if data is None:
            await self._send_error(ctx, "Could not fetch a valid image from that URL.")
            return
        await ctx.guild.edit(icon=data)
        await self._safe_send(ctx, "✅ Server icon updated.")

    @commands.command(name="setserverbanner")
    async def setserverbanner(self, ctx: commands.Context, url: str) -> None:
        await self._delete_invoke(ctx)
        if ctx.guild is None:
            await self._send_error(ctx, "This command requires a server.")
            return
        data = await self._fetch_image_bytes(url)
        if data is None:
            await self._send_error(ctx, "Could not fetch a valid image from that URL.")
            return
        await ctx.guild.edit(banner=data)
        await self._safe_send(ctx, "✅ Server banner updated.")

    @commands.command(name="lockserver")
    async def lockserver(self, ctx: commands.Context, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        guild = await self._get_guild(ctx, server)
        if guild is None:
            await self._send_error(ctx, "Server not found.")
            return
        count = 0
        for ch in guild.text_channels:
            overwrite = ch.overwrites_for(guild.default_role)
            overwrite.send_messages = False
            with suppress(discord.HTTPException, discord.Forbidden):
                await ch.set_permissions(guild.default_role, overwrite=overwrite)
                count += 1
        await self._safe_send(ctx, f"🔒 Locked {count} text channels.")

    @commands.command(name="unlockserver")
    async def unlockserver(self, ctx: commands.Context, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        guild = await self._get_guild(ctx, server)
        if guild is None:
            await self._send_error(ctx, "Server not found.")
            return
        count = 0
        for ch in guild.text_channels:
            overwrite = ch.overwrites_for(guild.default_role)
            overwrite.send_messages = None
            with suppress(discord.HTTPException, discord.Forbidden):
                await ch.set_permissions(guild.default_role, overwrite=overwrite)
                count += 1
        await self._safe_send(ctx, f"🔓 Unlocked {count} text channels.")

    # ------------------------------------------------------------------ #
    # Listing commands
    # ------------------------------------------------------------------ #
    def _channel_emoji(self, ch) -> str:
        t = str(ch.type)
        if t == "text":
            return "💬"
        if t == "voice":
            return "🔊"
        if t == "news":
            return "📢"
        if t == "stage_voice" or t == "stage":
            return "🎤"
        if t == "category":
            return "📁"
        if "thread" in t:
            return "🧵"
        return "•"

    @commands.command(name="channels")
    async def channels(self, ctx: commands.Context, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        guild = await self._get_guild(ctx, server)
        if guild is None:
            await self._send_error(ctx, "Server not found.")
            return
        ordered = sorted(guild.channels, key=lambda c: (c.position if c.position is not None else 0))
        lines = [f"{self._channel_emoji(c)} {getattr(c, 'name', c.id)} ({c.id})" for c in ordered]
        await self._safe_send(ctx, "```\n" + "\n".join(lines) + "\n```")

    @commands.command(name="bots")
    async def bots(self, ctx: commands.Context, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        guild = await self._get_guild(ctx, server)
        if guild is None:
            await self._send_error(ctx, "Server not found.")
            return
        bots = [m for m in guild.members if m.bot]
        lines = [f"{b.name}#{b.discriminator} ({b.id}) - {b.top_role.name}" for b in bots]
        await self._safe_send(ctx, f"**Bots: {len(bots)}**\n```\n" + ("\n".join(lines) or "None") + "\n```")

    @commands.command(name="admins")
    async def admins(self, ctx: commands.Context, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        guild = await self._get_guild(ctx, server)
        if guild is None:
            await self._send_error(ctx, "Server not found.")
            return
        admins = [m for m in guild.members if m.guild_permissions.administrator or m.guild_permissions.manage_guild]
        lines = [f"{a.name}#{a.discriminator} ({a.id}) - {a.top_role.name}" for a in admins]
        await self._safe_send(ctx, f"**Admins: {len(admins)}**\n```\n" + ("\n".join(lines) or "None") + "\n```")

    @commands.command(name="roles")
    async def roles(self, ctx: commands.Context, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        guild = await self._get_guild(ctx, server)
        if guild is None:
            await self._send_error(ctx, "Server not found.")
            return
        ordered = sorted(guild.roles, key=lambda r: r.position, reverse=True)
        lines = []
        for r in ordered:
            lines.append(f"{r.name} ({r.id}) | color: {r.colour} | members: {len(r.members)} | perms: {r.permissions.value}")
        await self._safe_send(ctx, "```\n" + "\n".join(lines) + "\n```")

    # ------------------------------------------------------------------ #
    # Leave / delete
    # ------------------------------------------------------------------ #
    @commands.command(name="leaveserver")
    async def leaveserver(self, ctx: commands.Context, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        guild = await self._get_guild(ctx, server)
        if guild is None:
            return
        with suppress(discord.HTTPException, discord.Forbidden):
            await guild.leave()

    @commands.command(name="deleteserver")
    async def deleteserver(self, ctx: commands.Context, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        guild = await self._get_guild(ctx, server)
        if guild is None:
            await self._send_error(ctx, "Server not found.")
            return
        if guild.owner_id != self.bot.user.id:
            await self._send_error(ctx, "You must be the server owner to delete it.")
            return
        with suppress(discord.HTTPException, discord.Forbidden):
            await guild.delete()

    # ------------------------------------------------------------------ #
    # Invite commands
    # ------------------------------------------------------------------ #
    def _extract_invite_code(self, value: str) -> str:
        value = value.strip()
        m = re.search(r"(?:discord\.gg|discord(?:app)?\.com/invite)/([\w-]+)", value)
        if m:
            return m.group(1)
        return value

    @commands.command(name="invite")
    async def invite(self, ctx: commands.Context, channel: Optional[str] = None,
                     max_age: Optional[int] = 86400, max_uses: Optional[int] = 0) -> None:
        await self._delete_invoke(ctx)
        ch = self._parse_channel(ctx, channel) if channel else ctx.channel
        if ch is None:
            await self._send_error(ctx, "Channel not found.")
            return
        inv = await ch.create_invite(max_age=max_age, max_uses=max_uses)
        await self._safe_send(ctx, f"🔗 {inv.url}\nExpires: {inv.expires_at or 'Never'} | Max uses: {inv.max_uses or '∞'}")

    @commands.command(name="friendinvite")
    async def friendinvite(self, ctx: commands.Context) -> None:
        await self._delete_invoke(ctx)
        try:
            inv = await self.bot.http.create_friend_invite()
            await self._safe_send(ctx, f"🔗 Friend invite: https://discord.gg/{inv['code']}")
        except discord.HTTPException as e:
            await self._send_error(ctx, f"Friend invite creation requires user account token: {e.text}")

    @commands.command(name="inviteinfo")
    async def inviteinfo(self, ctx: commands.Context, *, invite: str) -> None:
        await self._delete_invoke(ctx)
        code = self._extract_invite_code(invite)
        inv = await self.bot.fetch_invite(code, with_counts=True)
        embed = discord.Embed(title=f"Invite {inv.code}", color=EMBED_COLOR)
        embed.add_field(name="Guild", value=f"{inv.guild.name} ({inv.guild.id})" if inv.guild else "N/A", inline=True)
        embed.add_field(name="Channel", value=f"{inv.channel.name} ({inv.channel.id})" if inv.channel else "N/A", inline=True)
        if inv.inviter:
            embed.add_field(name="Inviter", value=f"{inv.inviter} ({inv.inviter.id})", inline=True)
        embed.add_field(name="Uses", value=f"{inv.uses}/{inv.max_uses or '∞'}", inline=True)
        embed.add_field(name="Expires", value=inv.expires_at or "Never", inline=True)
        embed.add_field(name="Temp Membership", value=inv.temporary, inline=True)
        if inv.approximate_member_count:
            embed.add_field(name="Members", value=inv.approximate_member_count, inline=True)
        if inv.approximate_presence_count:
            embed.add_field(name="Online", value=inv.approximate_presence_count, inline=True)
        await self._safe_send(ctx, embed=embed)

    @commands.command(name="deleteinvite")
    async def deleteinvite(self, ctx: commands.Context, *, invite: str) -> None:
        await self._delete_invoke(ctx)
        code = self._extract_invite_code(invite)
        await self.bot.http.delete_invite(code)
        await self._safe_send(ctx, "✅ Invite deleted.")

    @commands.command(name="serverinvites")
    async def serverinvites(self, ctx: commands.Context, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        guild = await self._get_guild(ctx, server)
        if guild is None:
            await self._send_error(ctx, "Server not found.")
            return
        invites = await guild.invites()
        if not invites:
            await self._safe_send(ctx, "No active invites.")
            return
        lines = [f"{i.code} | ch: {i.channel} | uses: {i.uses} | by: {i.inviter}" for i in invites]
        await self._safe_send(ctx, "```\n" + "\n".join(lines) + "\n```")

    @commands.command(name="channelinvites")
    async def channelinvites(self, ctx: commands.Context, channel: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        ch = self._parse_channel(ctx, channel) if channel else ctx.channel
        if ch is None:
            await self._send_error(ctx, "Channel not found.")
            return
        invites = await ch.invites()
        if not invites:
            await self._safe_send(ctx, "No active invites.")
            return
        lines = [f"{i.code} | uses: {i.uses} | by: {i.inviter}" for i in invites]
        await self._safe_send(ctx, "```\n" + "\n".join(lines) + "\n```")

    @commands.command(name="userinvites")
    async def userinvites(self, ctx: commands.Context, user: str, server: Optional[str] = None) -> None:
        await self._delete_invoke(ctx)
        target = self._parse_user(ctx, user)
        if target is None:
            await self._send_error(ctx, "User not found.")
            return
        guild = await self._get_guild(ctx, server)
        if guild is None:
            await self._send_error(ctx, "Server not found.")
            return
        all_invites = await guild.invites()
        user_invites = [i for i in all_invites if i.inviter and i.inviter.id == target.id]
        if not user_invites:
            await self._safe_send(ctx, "No invites from that user.")
            return
        lines = [f"{i.code} | ch: {i.channel} | uses: {i.uses}" for i in user_invites]
        await self._safe_send(ctx, "```\n" + "\n".join(lines) + "\n```")

    # ------------------------------------------------------------------ #
    # Role commands
    # ------------------------------------------------------------------ #
    @commands.command(name="roleinfo")
    async def roleinfo(self, ctx: commands.Context, *, role: str) -> None:
        await self._delete_invoke(ctx)
        r = self._parse_role(ctx, role)
        if r is None:
            await self._send_error(ctx, "Role not found.")
            return
        embed = discord.Embed(title=r.name, color=r.colour or EMBED_COLOR)
        embed.add_field(name="ID", value=r.id, inline=True)
        embed.add_field(name="Color", value=str(r.colour), inline=True)
        embed.add_field(name="Position", value=r.position, inline=True)
        embed.add_field(name="Members", value=len(r.members), inline=True)
        embed.add_field(name="Mentionable", value=r.mentionable, inline=True)
        embed.add_field(name="Hoist", value=r.hoist, inline=True)
        embed.add_field(name="Managed", value=r.managed, inline=True)
        embed.add_field(name="Created At", value=r.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        embed.add_field(name="Permissions (int)", value=r.permissions.value, inline=True)
        key_perms = [p for p, v in r.permissions if v]
        if key_perms:
            embed.add_field(name="Key Permissions", value=", ".join(key_perms[:15]), inline=False)
        await self._safe_send(ctx, embed=embed)

    @commands.command(name="giverole")
    async def giverole(self, ctx: commands.Context, user: str, *, role: str) -> None:
        await self._delete_invoke(ctx)
        target = self._parse_user(ctx, user)
        r = self._parse_role(ctx, role)
        if target is None or not isinstance(target, discord.Member):
            await self._send_error(ctx, "User not found in this server.")
            return
        if r is None:
            await self._send_error(ctx, "Role not found.")
            return
        await target.add_roles(r, reason="Role command")
        await self._safe_send(ctx, f"✅ Gave `{r.name}` to {target}.")

    @commands.command(name="removerole")
    async def removerole(self, ctx: commands.Context, user: str, *, role: str) -> None:
        await self._delete_invoke(ctx)
        target = self._parse_user(ctx, user)
        r = self._parse_role(ctx, role)
        if target is None or not isinstance(target, discord.Member):
            await self._send_error(ctx, "User not found in this server.")
            return
        if r is None:
            await self._send_error(ctx, "Role not found.")
            return
        await target.remove_roles(r, reason="Role command")
        await self._safe_send(ctx, f"✅ Removed `{r.name}` from {target}.")

    @commands.command(name="createrole")
    async def createrole(self, ctx: commands.Context, *, name: str) -> None:
        await self._delete_invoke(ctx)
        if ctx.guild is None:
            await self._send_error(ctx, "This command requires a server.")
            return
        r = await ctx.guild.create_role(name=name)
        await self._safe_send(ctx, f"✅ Created role `{r.name}` ({r.id})")

    @commands.command(name="deleterole")
    async def deleterole(self, ctx: commands.Context, *, role: str) -> None:
        await self._delete_invoke(ctx)
        r = self._parse_role(ctx, role)
        if r is None:
            await self._send_error(ctx, "Role not found.")
            return
        await r.delete()
        await self._safe_send(ctx, f"✅ Deleted role `{r.name}`.")

    @commands.command(name="renamerole")
    async def renamerole(self, ctx: commands.Context, role: str, *, name: str) -> None:
        await self._delete_invoke(ctx)
        r = self._parse_role(ctx, role)
        if r is None:
            await self._send_error(ctx, "Role not found.")
            return
        await r.edit(name=name)
        await self._safe_send(ctx, f"✅ Renamed role to `{name}`.")

    # ------------------------------------------------------------------ #
    # Error handling
    # ------------------------------------------------------------------ #
    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.MissingRequiredArgument):
            await self._send_error(ctx, f"Missing argument: {error.param.name}")
        elif isinstance(error, commands.BadArgument):
            await self._send_error(ctx, "Invalid argument type.")
        elif isinstance(error, commands.NoPrivateMessage):
            await self._send_error(ctx, "This command cannot be used in DMs.")
        elif isinstance(error, discord.Forbidden):
            await self._send_error(ctx, "I don't have permission to do that.")
        elif isinstance(error, discord.NotFound):
            await self._send_error(ctx, "Resource not found.")
        elif isinstance(error, discord.HTTPException):
            await self._send_error(ctx, f"An error occurred: {error.text or error}")
        else:
            print(f"[AdminCommands] Unhandled error in {ctx.command}: {error}")
            await self._send_error(ctx, f"An unexpected error occurred: {error}")


async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
