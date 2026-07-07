import asyncio
import os
import random
from typing import List, Optional, Tuple, Union

import discord
from discord.ext import commands


ANIMATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "animations")
os.makedirs(ANIMATIONS_DIR, exist_ok=True)


class AnimationCommands(commands.Cog):
    VIRUS_ANIMATIONS = {
        "trojan": {
            "frames": [
                "```diff\n- TROJAN DETECTED```",
                "```diff\n- TROJAN DETECTED\n- SCANNING FILES...```",
                "```diff\n- TROJAN DETECTED\n- SCANNING FILES...\n- INFECTED: system32.dll```",
                "```diff\n- TROJAN DETECTED\n- SCANNING FILES...\n- INFECTED: system32.dll\n- INFECTED: boot.ini```",
                "```diff\n- TROJAN DETECTED\n- SCANNING FILES...\n- INFECTED: system32.dll\n- INFECTED: boot.ini\n+ QUARANTINE FAILED```",
                "```diff\n- TROJAN DETECTED\n- SCANNING FILES...\n- INFECTED: system32.dll\n- INFECTED: boot.ini\n+ QUARANTINE FAILED\n- SYSTEM COMPROMISED```",
                "```diff\n- SYSTEM COMPROMISED\n- ALL FILES ENCRYPTED\n- SEND 0.5 BTC TO: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa```",
                "```diff\n- JUST KIDDING :)\n+ NO VIRUS DETECTED\n+ HAVE A NICE DAY```"
            ],
            "interval": 0.8
        },
        "worm": {
            "frames": [
                "🐛",
                "🐛💻",
                "🐛💻🔌",
                "🐛💻🔌📁",
                "🐛💻🔌📁📂",
                "🐛💻🔌📁📂📊",
                "🐛💻🔌📁📂📊📈",
                "```WORM.EXE HAS SPREAD TO ALL NETWORK DRIVES```",
                "```CANNOT BE CONTAINED```",
                "```WORM.EXE\n████████████████████ 100%```"
            ],
            "interval": 0.5
        },
        "ransomware": {
            "frames": [
                "🔒",
                "🔒🔒",
                "🔒🔒🔒",
                "```YOUR FILES HAVE BEEN ENCRYPTED```",
                "```YOUR FILES HAVE BEEN ENCRYPTED\n[████░░░░░░░░░░░░] 30%```",
                "```YOUR FILES HAVE BEEN ENCRYPTED\n[██████░░░░░░░░░░] 50%```",
                "```YOUR FILES HAVE BEEN ENCRYPTED\n[██████████░░░░░░] 75%```",
                "```YOUR FILES HAVE BEEN ENCRYPTED\n[████████████████] 100%```",
                "```PAYMENT REQUIRED: $10,000 IN MONOPOLY MONEY```",
                "```PAYMENT RECEIVED. FILES DECRYPTED. (NOT REALLY)```"
            ],
            "interval": 0.7
        },
        "spyware": {
            "frames": [
                "👁️",
                "👁️📸",
                "👁️📸🎤",
                "👁️📸🎤📍",
                "```SPYWARE ACTIVE```",
                "```SPYWARE ACTIVE\n- WEBCAM: ENABLED```",
                "```SPYWARE ACTIVE\n- WEBCAM: ENABLED\n- MICROPHONE: RECORDING```",
                "```SPYWARE ACTIVE\n- WEBCAM: ENABLED\n- MICROPHONE: RECORDING\n- LOCATION: TRACKED```",
                "```SPYWARE ACTIVE\n- WEBCAM: ENABLED\n- MICROPHONE: RECORDING\n- LOCATION: TRACKED\n- KEYSTROKES: LOGGED```",
                "```SPYWARE REPORT: YOU HAVE TERRIBLE TASTE IN MUSIC```"
            ],
            "interval": 0.6
        }
    }

    BOMB_FRAMES = [
        ("💣", 1.0),
        ("💣 3", 1.0),
        ("💣 2", 1.0),
        ("💣 1", 1.0),
        ("💥", 0.3),
        ("💥💥", 0.3),
        ("💥💥💥", 0.3),
        ("💥💥💥💥", 0.2),
        ("💥💥💥💥💥", 0.2),
        ("```BOOM!```", 0.5),
        ("```BOOM!\nYOU'RE DEAD```", 0.5),
        ("```BOOM!\nYOU'RE DEAD\n💀```", 1.0),
        ("```just kidding lol```", 0.0)
    ]

    FUCKYOU_FRAMES = [
        ("f", 0.2),
        ("fu", 0.2),
        ("fuc", 0.2),
        ("fuck", 0.3),
        ("fuck y", 0.2),
        ("fuck yo", 0.2),
        ("fuck you", 0.5),
        ("fuck you 🖕", 0.3),
        ("fuck you 🖕🖕", 0.3),
        ("fuck you 🖕🖕🖕", 0.3),
        ("```FUCK YOU VERY MUCH```", 0.5),
        ("```FUCK YOU VERY MUCH\n🖕😊🖕```", 0.0)
    ]

    FAP_FRAMES = [
        ("🍆", 0.3),
        ("🍆💦", 0.2),
        ("🍆💦💦", 0.2),
        ("🍆💦💦💦", 0.15),
        ("🍆💦💦💦💦", 0.15),
        ("🍆💦💦💦💦💦", 0.1),
        ("🍆💦💦💦💦💦💦", 0.1),
        ("🍆💦💦💦💦💦💦💦", 0.1),
        ("🍆💦💦💦💦💦💦💦💦", 0.1),
        ("🍆💦💦💦💦💦💦💦💦💦", 0.08),
        ("🍆💦💦💦💦💦💦💦💦💦💦", 0.08),
        ("🍆💦💦💦💦💦💦💦💦💦💦💦", 0.08),
        ("🍆💦💦💦💦💦💦💦💦💦💦💦💦", 0.08),
        ("🍆💦💦💦💦💦💦💦💦💦💦💦💦💦", 0.08),
        ("🍆💦💦💦💦💦💦💦💦💦💦💦💦💦💦", 0.05),
        ("🍆💦💦💦💦💦💦💦💦💦💦💦💦💦💦💦", 0.05),
        ("🍆💦💦💦💦💦💦💦💦💦💦💦💦💦💦💦💦", 0.05),
        ("🍆💦💦💦💦💦💦💦💦💦💦💦💦💦💦💦💦💦", 0.5),
        ("```💀 POST-NUT CLARITY 💀\nwhat am i doing with my life```", 0.0)
    ]

    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot

    async def _delete_invoke(self, ctx: commands.Context) -> None:
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass

    async def _run_animation(
        self,
        ctx: commands.Context,
        frames: List[Union[str, Tuple[str, float]]],
        interval: float = 0.1
    ) -> None:
        if not frames:
            return

        is_variable = isinstance(frames[0], tuple)
        content = frames[0][0] if is_variable else frames[0]

        msg = await ctx.send(content)

        if is_variable:
            for frame, delay in frames[1:]:
                if delay > 0:
                    await asyncio.sleep(delay)
                try:
                    await msg.edit(content=frame)
                except discord.Forbidden:
                    break
                except discord.NotFound:
                    break
                except discord.HTTPException as e:
                    if e.status == 429:
                        await asyncio.sleep(0.5)
                        try:
                            await msg.edit(content=frame)
                        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                            break
                    else:
                        break
        else:
            for frame in frames[1:]:
                await asyncio.sleep(interval)
                try:
                    await msg.edit(content=frame)
                except discord.Forbidden:
                    break
                except discord.NotFound:
                    break
                except discord.HTTPException as e:
                    if e.status == 429:
                        await asyncio.sleep(0.5)
                        try:
                            await msg.edit(content=frame)
                        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                            break
                    else:
                        break

    def _sanitize_name(self, name: str) -> str:
        name = name.replace('\\', '').replace('/', '').replace('..', '')
        if name.endswith('.txt'):
            name = name[:-4]
        return name[:100]

    def get_custom_animations(self) -> List[str]:
        if not os.path.isdir(ANIMATIONS_DIR):
            return []
        return sorted([
            f[:-4]
            for f in os.listdir(ANIMATIONS_DIR)
            if f.endswith('.txt') and os.path.isfile(os.path.join(ANIMATIONS_DIR, f))
        ])

    @commands.command()
    async def virus(self, ctx: commands.Context, virus_name: Optional[str] = None):
        await self._delete_invoke(ctx)

        if virus_name is None:
            virus_name = random.choice(list(self.VIRUS_ANIMATIONS.keys()))
        elif virus_name not in self.VIRUS_ANIMATIONS:
            msg = await ctx.send("Unknown virus. Available: trojan, worm, ransomware, spyware")
            await msg.delete(delay=3)
            return

        anim = self.VIRUS_ANIMATIONS[virus_name]
        await self._run_animation(ctx, anim["frames"], anim["interval"])

    @commands.command(name="100")
    async def hundred(self, ctx: commands.Context):
        await self._delete_invoke(ctx)
        frames = [str(i) for i in range(1, 101)]
        await self._run_animation(ctx, frames, 0.1)

    @commands.command()
    async def bomb(self, ctx: commands.Context):
        await self._delete_invoke(ctx)
        await self._run_animation(ctx, self.BOMB_FRAMES, 0.1)

    @commands.command()
    async def fuckyou(self, ctx: commands.Context):
        await self._delete_invoke(ctx)
        await self._run_animation(ctx, self.FUCKYOU_FRAMES, 0.1)

    @commands.command()
    async def fap(self, ctx: commands.Context):
        await self._delete_invoke(ctx)
        await self._run_animation(ctx, self.FAP_FRAMES, 0.1)

    @commands.command()
    async def countup(self, ctx: commands.Context, number: str):
        try:
            num = int(number)
        except ValueError:
            await ctx.send("Provide a valid number.")
            await self._delete_invoke(ctx)
            return

        await self._delete_invoke(ctx)

        if num < 1:
            num = 1
        elif num > 1000:
            num = 1000
            warn = await ctx.send("Capped at 1000.")
            await warn.delete(delay=3)

        frames = [str(i) for i in range(1, num + 1)]
        delays: List[float] = []
        for n in range(1, num):
            if n <= 10:
                delays.append(0.05)
            elif n <= 100:
                delays.append(0.02)
            else:
                delays.append(0.01)

        total = sum(delays)
        if total > 15.0 and total > 0:
            scale = 15.0 / total
            delays = [d * scale for d in delays]

        variable_frames: List[Tuple[str, float]] = [(frames[0], 0.0)]
        for i, delay in enumerate(delays):
            variable_frames.append((frames[i + 1], delay))

        await self._run_animation(ctx, variable_frames, 0.1)

    @commands.command()
    async def countdown(self, ctx: commands.Context, number: str):
        try:
            num = int(number)
        except ValueError:
            await ctx.send("Provide a valid number.")
            await self._delete_invoke(ctx)
            return

        await self._delete_invoke(ctx)

        if num < 1:
            num = 1
        elif num > 1000:
            num = 1000
            warn = await ctx.send("Capped at 1000.")
            await warn.delete(delay=3)

        frames = [str(num)]
        delays: List[float] = []

        for n in range(num - 1, -1, -1):
            frames.append(str(n))
            if n >= 100:
                delays.append(0.02)
            elif n >= 10:
                delays.append(0.04)
            else:
                delays.append(0.08)

        frames.append("```🔥 LIFTOFF 🚀```")
        delays.append(0.5)

        total = sum(delays)
        if total > 15.0 and total > 0:
            scale = 15.0 / total
            delays = [d * scale for d in delays]

        variable_frames: List[Tuple[str, float]] = [(frames[0], 0.0)]
        for i, delay in enumerate(delays):
            variable_frames.append((frames[i + 1], delay))

        await self._run_animation(ctx, variable_frames, 0.1)

    @commands.command()
    async def asciianimation(self, ctx: commands.Context, *, text: str):
        await self._delete_invoke(ctx)

        if len(text) <= 100:
            frames = [text[:i] for i in range(1, len(text) + 1)]
        else:
            chunk_size = 3
            frames = [text[:i * chunk_size] for i in range(1, len(text) // chunk_size + 1)]
            if frames[-1] != text:
                frames.append(text)

        interval = 0.1
        total_time = len(frames) * interval
        if total_time > 10.0 and total_time > 0:
            scale = 10.0 / total_time
            interval = max(0.01, interval * scale)

        await self._run_animation(ctx, frames, interval)

    @commands.command()
    async def customanimationhelp(self, ctx: commands.Context):
        await self._delete_invoke(ctx)

        help_text = (
            "📽️ Custom Animation Help\n\n"
            "Create .txt files in the Animations folder.\n"
            "Each line = one frame.\n\n"
            "Example file: wave.txt\n"
            "→\n"
            "e\n"
            "he\n"
            "hel\n"
            "hell\n"
            "hello\n\n"
            f"Usage: {ctx.prefix}customanimation <name>\n"
            "(no .txt extension needed)"
        )

        try:
            embed = discord.Embed(
                title="Custom Animation Help",
                description=help_text,
                color=0x00FF00
            )
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(help_text)

    @commands.command()
    async def customanimations(self, ctx: commands.Context):
        await self._delete_invoke(ctx)

        animations = self.get_custom_animations()

        if not animations:
            await ctx.send("No custom animations found. Create .txt files in the Animations folder.")
            return

        lines = [f"• {name}" for name in animations]
        message = (
            f"📁 Available Custom Animations ({len(animations)})\n\n"
            + "\n".join(lines)
            + f"\n\nUse {ctx.prefix}customanimation <name> to play one."
        )
        await ctx.send(message)

    @commands.command()
    async def customanimation(self, ctx: commands.Context, *, name: str):
        name = self._sanitize_name(name)

        if not name:
            await ctx.send("Please provide an animation name.")
            await self._delete_invoke(ctx)
            return

        path = os.path.join(ANIMATIONS_DIR, f"{name}.txt")

        if not os.path.isfile(path):
            await ctx.send(
                f"Animation '{name}' not found. Use `{ctx.prefix}customanimations` to see available ones."
            )
            await self._delete_invoke(ctx)
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                frames = [line.rstrip("\n") for line in f if line.strip()]
        except Exception:
            await ctx.send("Error reading animation file.")
            await self._delete_invoke(ctx)
            return

        await self._delete_invoke(ctx)

        if not frames:
            await ctx.send("Animation file is empty.")
            return

        if len(frames) == 1:
            await ctx.send(frames[0])
        else:
            await self._run_animation(ctx, frames, 0.3)


async def setup(bot: commands.Bot):
    await bot.add_cog(AnimationCommands(bot))
