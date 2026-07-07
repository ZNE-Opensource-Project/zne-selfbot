import asyncio
import random
import string
import unicodedata

import discord
from discord.ext import commands

try:
    import pyfiglet
    HAS_PYFIGLET: bool = True
except ImportError:
    HAS_PYFIGLET = False


FLIP_MAP = {
    'a': 'ɐ', 'b': 'q', 'c': 'ɔ', 'd': 'p', 'e': 'ǝ', 'f': 'ɟ', 'g': 'ƃ', 'h': 'ɥ',
    'i': 'ᴉ', 'j': 'ɾ', 'k': 'ʞ', 'l': 'l', 'm': 'ɯ', 'n': 'u', 'o': 'o', 'p': 'd',
    'q': 'b', 'r': 'ɹ', 's': 's', 't': 'ʇ', 'u': 'n', 'v': 'ʌ', 'w': 'ʍ', 'x': 'x',
    'y': 'ʎ', 'z': 'z',
    'A': '∀', 'B': '𐐒', 'C': 'Ɔ', 'D': 'ᗡ', 'E': 'Ǝ', 'F': 'Ⅎ', 'G': '⅁', 'H': 'H',
    'I': 'I', 'J': 'ſ', 'K': '⋊', 'L': '⅂', 'M': 'W', 'N': 'N', 'O': 'O', 'P': 'Ԁ',
    'Q': 'Ό', 'R': 'ᴚ', 'S': 'S', 'T': '⊥', 'U': '∩', 'V': 'Λ', 'W': 'M', 'X': 'X',
    'Y': '⅄', 'Z': 'Z',
    '0': '0', '1': 'Ɩ', '2': 'ᄅ', '3': 'Ɛ', '4': 'ㄣ', '5': 'ϛ', '6': '9', '7': 'ㄥ',
    '8': '8', '9': '6',
    '.': '˙', ',': "'", "'": ',', '"': '„', '!': '¡', '?': '¿',
    '&': '⅋', '_': '‾', '(': ')', ')': '(', '[': ']', ']': '[',
}

ZALGO_UPPER = ['\u0300','\u0301','\u0302','\u0303','\u0304','\u0305','\u0306','\u0307',
               '\u0308','\u0309','\u030A','\u030B','\u030C','\u030D','\u030E','\u030F',
               '\u0310','\u0311','\u0312','\u0313','\u0314','\u0315','\u0316','\u0317',
               '\u0318','\u0319','\u031A']

ZALGO_MID = ['\u0320','\u0321','\u0322','\u0323','\u0324','\u0325','\u0326','\u0327',
             '\u0328','\u0329','\u032A','\u032B','\u032C','\u032D','\u032E','\u032F',
             '\u0330','\u0331','\u0332','\u0333','\u0334','\u0335','\u0336','\u0337',
             '\u0338','\u0339','\u033A','\u033B','\u033C','\u033D','\u033E','\u033F']

ZALGO_LOWER = ['\u0340','\u0341','\u0342','\u0343','\u0344','\u0345','\u0346','\u0347',
               '\u0348','\u0349','\u034A','\u034B','\u034C','\u034D','\u034E']

ZALGO_MISC = ['\u0350','\u0351','\u0352','\u0353','\u0354','\u0355','\u0356','\u0357',
              '\u0358','\u0359','\u035A','\u035B','\u035C','\u035D','\u035E','\u035F']

ZERO_WIDTH_POOL = ['\u200b', '\u200c', '\u200d', '\u2060', '\ufeff']

LEET_MAP = str.maketrans({
    'a': '4', 'A': '4',
    'e': '3', 'E': '3',
    'i': '1', 'I': '1',
    'o': '0', 'O': '0',
    's': '5', 'S': '5',
    't': '7', 'T': '7',
    'b': '8', 'B': '8',
    'g': '9', 'G': '9',
    'z': '2', 'Z': '2',
})


def levenshtein(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


class TextCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot

    async def _delete_invoke(self, ctx: commands.Context) -> None:
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass

    async def _safe_send(self, ctx: commands.Context, content: str) -> discord.Message | None:
        try:
            return await ctx.send(content)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
            print(f"[TextCommands] send failed: {e}")
            return None

    async def _warn_and_delete(self, ctx: commands.Context, warning: str) -> None:
        msg = await self._safe_send(ctx, warning)
        if msg is not None:
            await asyncio.sleep(3)
            try:
                await msg.delete()
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                pass

    @commands.command(name="empty")
    async def empty(self, ctx: commands.Context) -> None:
        await self._delete_invoke(ctx)
        await self._safe_send(ctx, "\u200c")

    @commands.command(name="reverse")
    async def reverse(self, ctx: commands.Context, *, text: str = "") -> None:
        await self._delete_invoke(ctx)
        if not text:
            await self._warn_and_delete(ctx, "Provide text to reverse.")
            return
        await self._safe_send(ctx, text[::-1])

    @commands.command(name="alphabet")
    async def alphabet(self, ctx: commands.Context) -> None:
        await self._delete_invoke(ctx)
        alphabet = "abcdefghijklmnopqrstuvwxyz"
        msg = await self._safe_send(ctx, alphabet)
        if msg is None:
            return
        for i in range(1, 26):
            shifted = alphabet[i:] + alphabet[:i]
            await asyncio.sleep(0.5)
            try:
                await msg.edit(content=shifted)
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                break
        await asyncio.sleep(0.5)
        try:
            await msg.edit(content=alphabet)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass

    @commands.command(name="ascii")
    async def ascii(self, ctx: commands.Context, *, text: str = "") -> None:
        await self._delete_invoke(ctx)
        if not text:
            await self._warn_and_delete(ctx, "Provide text for ASCII art.")
            return
        if not HAS_PYFIGLET:
            await self._safe_send(ctx, "pyfiglet is not installed. Run `pip install pyfiglet`.")
            return
        art = pyfiglet.figlet_format(text)
        content = f"```\n{art}\n```"
        await self._safe_send(ctx, content)

    @commands.command(name="bold")
    async def bold(self, ctx: commands.Context, *, text: str = "") -> None:
        await self._delete_invoke(ctx)
        if not text:
            await self._warn_and_delete(ctx, "Provide text to bold.")
            return
        await self._safe_send(ctx, f"**{text}**")

    @commands.command(name="strike")
    async def strike(self, ctx: commands.Context, *, text: str = "") -> None:
        await self._delete_invoke(ctx)
        if not text:
            await self._warn_and_delete(ctx, "Provide text to strikethrough.")
            return
        await self._safe_send(ctx, f"~~{text}~~")

    @commands.command(name="italic")
    async def italic(self, ctx: commands.Context, *, text: str = "") -> None:
        await self._delete_invoke(ctx)
        if not text:
            await self._warn_and_delete(ctx, "Provide text to italicize.")
            return
        await self._safe_send(ctx, f"*{text}*")

    @commands.command(name="spoiler")
    async def spoiler(self, ctx: commands.Context, *, text: str = "") -> None:
        await self._delete_invoke(ctx)
        if not text:
            await self._warn_and_delete(ctx, "Provide text to spoiler.")
            return
        await self._safe_send(ctx, f"||{text}||")

    @commands.command(name="lspoiler")
    async def lspoiler(self, ctx: commands.Context, *, text: str = "") -> None:
        await self._delete_invoke(ctx)
        if not text:
            await self._warn_and_delete(ctx, "Provide text to letter-spoiler.")
            return
        result = "".join(f"||{c}||" if c != " " else " " for c in text)
        await self._safe_send(ctx, result)

    @commands.command(name="leet")
    async def leet(self, ctx: commands.Context, *, text: str = "") -> None:
        await self._delete_invoke(ctx)
        if not text:
            await self._warn_and_delete(ctx, "Provide text to leet.")
            return
        await self._safe_send(ctx, text.translate(LEET_MAP))

    @commands.command(name="devowel")
    async def devowel(self, ctx: commands.Context, *, text: str = "") -> None:
        await self._delete_invoke(ctx)
        if not text:
            await self._warn_and_delete(ctx, "Provide text to devowel.")
            return
        result = "".join(c for c in text if c.lower() not in "aeiou")
        await self._safe_send(ctx, result)

    @commands.command(name="edit")
    async def edit(self, ctx: commands.Context, *, text: str = "") -> None:
        await self._delete_invoke(ctx)
        if not text:
            await self._warn_and_delete(ctx, "Provide text to type out.")
            return
        words = text.split(" ")
        msg = await self._safe_send(ctx, words[0])
        if msg is None:
            return
        current = words[0]
        for word in words[1:]:
            current = f"{current} {word}"
            await asyncio.sleep(0.3)
            try:
                await msg.edit(content=current)
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                break

    @commands.command(name="emojify")
    async def emojify(self, ctx: commands.Context, *, text: str = "") -> None:
        await self._delete_invoke(ctx)
        if not text:
            await self._warn_and_delete(ctx, "Provide text to emojify.")
            return
        result = []
        for char in text:
            if char.isalpha():
                lower = char.lower()
                emoji = chr(ord(lower) - ord('a') + 0x1F1E6)
                result.append(emoji)
            elif char.isdigit():
                result.append(f"{char}\uFE0F\u20E3")
            elif char == " ":
                result.append("   ")
            else:
                result.append(char)
        await self._safe_send(ctx, "".join(result))

    @commands.command(name="shrug")
    async def shrug(self, ctx: commands.Context, *, text: str = "") -> None:
        await self._delete_invoke(ctx)
        content = f"¯\\_(ツ)_/¯ {text}".strip()
        await self._safe_send(ctx, content)

    @commands.command(name="lenny")
    async def lenny(self, ctx: commands.Context) -> None:
        await self._delete_invoke(ctx)
        await self._safe_send(ctx, "( ͡° ͜ʖ ͡°)")

    @commands.command(name="tableflip")
    async def tableflip(self, ctx: commands.Context) -> None:
        await self._delete_invoke(ctx)
        await self._safe_send(ctx, "(╯°□°）╯︵ ┻━┻")

    @commands.command(name="unflip")
    async def unflip(self, ctx: commands.Context) -> None:
        await self._delete_invoke(ctx)
        await self._safe_send(ctx, "┬─┬ ノ( ゜-゜ノ)")

    @commands.command(name="clap")
    async def clap(self, ctx: commands.Context, *, text: str = "") -> None:
        await self._delete_invoke(ctx)
        if not text:
            await self._warn_and_delete(ctx, "Provide text to clap.")
            return
        await self._safe_send(ctx, text.replace(" ", "👏"))

    @commands.command(name="zalgo")
    async def zalgo(self, ctx: commands.Context, *, text: str = "") -> None:
        await self._delete_invoke(ctx)
        if not text:
            await self._warn_and_delete(ctx, "Provide text to zalgo.")
            return
        if len(text) > 200:
            text = text[:200]
        result = []
        for char in text:
            marks = []
            marks.extend(random.sample(ZALGO_UPPER, random.randint(1, 5)))
            marks.extend(random.sample(ZALGO_MID, random.randint(1, 3)))
            marks.extend(random.sample(ZALGO_LOWER, random.randint(1, 2)))
            marks.extend(random.sample(ZALGO_MISC, random.randint(1, 2)))
            random.shuffle(marks)
            result.append(char + "".join(marks))
        await self._safe_send(ctx, "".join(result))

    @commands.command(name="unzalgo")
    async def unzalgo(self, ctx: commands.Context, *, text: str = "") -> None:
        await self._delete_invoke(ctx)
        if not text:
            await self._warn_and_delete(ctx, "Provide text to unzalgo.")
            return
        cleaned = "".join(c for c in text if unicodedata.category(c) != "Mn")
        await self._safe_send(ctx, cleaned)

    @commands.command(name="upper")
    async def upper(self, ctx: commands.Context, *, text: str = "") -> None:
        await self._delete_invoke(ctx)
        if not text:
            await self._warn_and_delete(ctx, "Provide text to uppercase.")
            return
        await self._safe_send(ctx, text.upper())

    @commands.command(name="lower")
    async def lower(self, ctx: commands.Context, *, text: str = "") -> None:
        await self._delete_invoke(ctx)
        if not text:
            await self._warn_and_delete(ctx, "Provide text to lowercase.")
            return
        await self._safe_send(ctx, text.lower())

    @commands.command(name="fliptext")
    async def fliptext(self, ctx: commands.Context, *, text: str = "") -> None:
        await self._delete_invoke(ctx)
        if not text:
            await self._warn_and_delete(ctx, "Provide text to flip.")
            return
        flipped = "".join(FLIP_MAP.get(c, c) for c in reversed(text))
        await self._safe_send(ctx, flipped)

    @commands.command(name="unfliptext")
    async def unfliptext(self, ctx: commands.Context, *, text: str = "") -> None:
        await self._delete_invoke(ctx)
        if not text:
            await self._warn_and_delete(ctx, "Provide text to unflip.")
            return
        reverse_map = {v: k for k, v in FLIP_MAP.items()}
        unflipped = "".join(reverse_map.get(c, c) for c in reversed(text))
        await self._safe_send(ctx, unflipped)

    @commands.command(name="wave")
    async def wave(self, ctx: commands.Context, *, text: str = "") -> None:
        await self._delete_invoke(ctx)
        if not text:
            await self._warn_and_delete(ctx, "Provide text to wave.")
            return
        transformed = " ".join(c.lower() if i % 2 == 0 else c.upper() for i, c in enumerate(text))
        await self._safe_send(ctx, transformed)

    @commands.command(name="customwave")
    async def customwave(self, ctx: commands.Context, width: str = "1", iterations: str = "1", *, text: str = "") -> None:
        await self._delete_invoke(ctx)
        try:
            w = max(1, int(width))
            it = max(1, int(iterations))
        except ValueError:
            w, it = 1, 1
        if not text:
            await self._warn_and_delete(ctx, "Provide text to customwave.")
            return
        chars = list(text * it)
        transformed = [
            c.lower() if (i // w) % 2 == 0 else c.upper()
            for i, c in enumerate(chars)
        ]
        await self._safe_send(ctx, " ".join(transformed))

    @commands.command(name="zwc")
    async def zwc(self, ctx: commands.Context, *, text: str = "") -> None:
        await self._delete_invoke(ctx)
        if not text:
            await self._warn_and_delete(ctx, "Provide text to encode.")
            return
        result = "".join(c + random.choice(ZERO_WIDTH_POOL) for c in text)
        await self._safe_send(ctx, result)

    @commands.command(name="distance")
    async def distance(self, ctx: commands.Context, *, text: str = "") -> None:
        await self._delete_invoke(ctx)
        try:
            parts = text.split('"')
            s1 = parts[1]
            s2 = parts[3]
        except (IndexError, ValueError):
            await self._warn_and_delete(ctx, 'Usage: distance "string one" "string two"')
            return
        result = levenshtein(s1, s2)
        await self._safe_send(ctx, f"Levenshtein distance: {result}")

    @commands.command(name="codeblock")
    async def codeblock(self, ctx: commands.Context, language: str = "", *, code: str = "") -> None:
        await self._delete_invoke(ctx)
        if not code:
            await self._warn_and_delete(ctx, "Provide code to format.")
            return
        content = f"```{language}\n{code}\n```"
        await self._safe_send(ctx, content)


async def setup(bot):
    await bot.add_cog(TextCommands(bot))
