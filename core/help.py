import asyncio
import discord
from discord.ext import commands

BACK_EMOJI = "◀️"
FORWARD_EMOJI = "▶️"


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot

    def _build_pages(self) -> list[dict]:
        pages: list[dict] = []

        for cog in self.bot.cogs.values():
            category = type(cog).__name__
            if category.endswith("Cog"):
                category = category[:-3]
            if category == "Help":
                continue

            visible = [cmd for cmd in cog.get_commands() if not cmd.hidden]
            if visible:
                pages.append({
                    "category_name": category,
                    "commands": sorted(
                        [(c.name, c.help or "No description provided.") for c in visible],
                        key=lambda x: x[0],
                    ),
                })

        uncategorized = [
            cmd for cmd in self.bot.commands
            if cmd.cog is None and not cmd.hidden
        ]
        if uncategorized:
            pages.append({
                "category_name": "Uncategorized",
                "commands": sorted(
                    [(c.name, c.help or "No description provided.") for c in uncategorized],
                    key=lambda x: x[0],
                ),
            })

        if not pages:
            pages.append({
                "category_name": "No Commands",
                "commands": [],
            })

        return pages

    def _render_page(self, page: dict) -> str:
        name = page["category_name"]
        cmds = page["commands"]
        if not cmds:
            return f"## 📚 {name}\nNo commands in this category."
        lines = [f"## 📚 {name}", f"{len(cmds)} commands", ""]
        for cmd_name, desc in cmds:
            lines.append(f"`{cmd_name}` = `{desc}`")
        return "\n".join(lines)

    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context) -> None:
        total_commands = len(self.bot.commands)
        total_categories = sum(
            1 for cog in self.bot.cogs.values() if len(cog.get_commands()) > 0
        )

        content = (
            f"## Welcome! {ctx.author.mention}\n"
            f"Welcome to ZNE Selfbot v1, its still being worked on but you can access all \n"
            f"**{total_commands}** commands across **{total_categories}** categories!\n\n"
            f"react the emojis ◀ or ▶ to view commands list"
        )

        try:
            help_message = await ctx.send(content)
        except (discord.Forbidden, discord.NotFound):
            return

        pages = self._build_pages()
        current_page_index = -1

        while True:
            try:
                payload = await self.bot.wait_for(
                    "raw_reaction_add",
                    check=lambda p: (
                        p.message_id == help_message.id
                        and p.user_id == ctx.author.id
                        and p.emoji.name in [BACK_EMOJI, FORWARD_EMOJI]
                    ),
                    timeout=60.0,
                )
            except asyncio.TimeoutError:
                try:
                    await help_message.clear_reactions()
                except (discord.Forbidden, discord.NotFound):
                    pass
                break

            try:
                await help_message.remove_reaction(payload.emoji, payload.member)
            except (discord.Forbidden, discord.NotFound):
                pass

            if payload.emoji.name == FORWARD_EMOJI:
                current_page_index = 0 if current_page_index >= len(pages) - 1 else current_page_index + 1
            elif payload.emoji.name == BACK_EMOJI:
                current_page_index = len(pages) - 1 if current_page_index <= 0 else current_page_index - 1

            try:
                await help_message.edit(content=self._render_page(pages[current_page_index]))
            except (discord.Forbidden, discord.NotFound):
                break


async def setup(bot):
    await bot.add_cog(Help(bot))
