import asyncio
import base64
import binascii
import codecs
import hashlib
import re
import struct
import zlib
import urllib.parse
from discord.ext import commands

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad
    PYCRYPTODOME_AVAILABLE = True
except ImportError:
    PYCRYPTODOME_AVAILABLE = False


class EncodingCommands(commands.Cog):
    MORSE_ENCODE = {
        'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.',
        'G': '--.', 'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..',
        'M': '--', 'N': '-.', 'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.',
        'S': '...', 'T': '-', 'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-',
        'Y': '-.--', 'Z': '--..',
        '0': '-----', '1': '.----', '2': '..---', '3': '...--', '4': '....-',
        '5': '.....', '6': '-....', '7': '--...', '8': '---..', '9': '----.',
        '.': '.-.-.-', ',': '--..--', '?': '..--..', "'": '.----.', '!': '-.-.--',
        '/': '-..-.', '(': '-.--.', ')': '-.--.-', '&': '.-...', ':': '---...',
        ';': '-.-.-.', '=': '-...-', '+': '.-.-.', '-': '-....-', '_': '..--.-',
        '"': '.-..-.', '$': '...-..-', '@': '.--.-.', ' ': '/'
    }
    MORSE_DECODE = {v: k for k, v in MORSE_ENCODE.items()}

    BASE58_ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    BASE36_ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyz'

    FNV_32_PRIME = 0x01000193
    FNV_32_OFFSET = 0x811C9DC5
    FNV_64_PRIME = 0x00000100000001B3
    FNV_64_OFFSET = 0xCBF29CE484222325
    FNV_128_PRIME = 0x0000000001000000000000000000013B
    FNV_128_OFFSET = 0x6C62272E07BB014262B821756295C58D

    POLYNOMIAL = 0xC96C5795D7870F42
    CRC64_TABLE = []
    for i in range(256):
        crc = i
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ POLYNOMIAL
            else:
                crc >>= 1
        CRC64_TABLE.append(crc)

    def __init__(self, bot):
        self.bot = bot

    async def _delete_invoke(self, ctx):
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass

    @staticmethod
    def _parse_quoted_args(content: str):
        pattern = re.compile(r'"([^"]*)"')
        return pattern.findall(content)

    @staticmethod
    def _is_mode(value: str, mode_type: str = '') -> bool:
        v = value.lower()
        if mode_type in ('encode', 'decode'):
            return v in ('encode', 'e', 'enc', 'decode', 'd', 'dec')
        if mode_type in ('encrypt', 'decrypt'):
            return v in ('encrypt', 'e', 'enc', 'decrypt', 'd', 'dec')
        return False

    @staticmethod
    def _normalize_mode(value: str) -> str:
        v = value.lower()
        encode_group = ('encode', 'e', 'enc')
        decode_group = ('decode', 'd', 'dec')
        if v in encode_group:
            return 'encode'
        if v in decode_group:
            return 'decode'
        encrypt_group = ('encrypt', 'e', 'enc')
        decrypt_group = ('decrypt', 'd', 'dec')
        if v in encrypt_group:
            return 'encrypt'
        if v in decrypt_group:
            return 'decrypt'
        return v

    @commands.command()
    async def rot13(self, ctx, *, text: str):
        await self._delete_invoke(ctx)
        result = codecs.encode(text, 'rot_13')
        await ctx.send(result)

    @commands.command()
    async def hex(self, ctx, mode: str, *, text: str):
        await self._delete_invoke(ctx)
        mode = self._normalize_mode(mode)
        try:
            if mode == 'encode':
                result = text.encode('utf-8').hex()
            elif mode == 'decode':
                result = bytes.fromhex(text).decode('utf-8')
            else:
                await ctx.send('Usage: `[p]hex <encode|decode> <text>`')
                return
            await ctx.send(result)
        except (ValueError, binascii.Error):
            await ctx.send('Invalid hex string.')

    @commands.command()
    async def binary(self, ctx, mode: str, *, text: str):
        await self._delete_invoke(ctx)
        mode = self._normalize_mode(mode)
        try:
            if mode == 'encode':
                result = ' '.join(format(ord(c), '08b') for c in text)
            elif mode == 'decode':
                result = ''.join(chr(int(b, 2)) for b in text.split())
            else:
                await ctx.send('Usage: `[p]binary <encode|decode> <text>`')
                return
            await ctx.send(result)
        except (ValueError, TypeError):
            await ctx.send('Invalid binary string.')

    @commands.command()
    async def base32(self, ctx, mode: str, *, text: str):
        await self._delete_invoke(ctx)
        mode = self._normalize_mode(mode)
        try:
            if mode == 'encode':
                result = base64.b32encode(text.encode('utf-8')).decode('utf-8')
            elif mode == 'decode':
                padded = text + '=' * (8 - len(text) % 8) if len(text) % 8 else text
                result = base64.b32decode(padded.encode('utf-8')).decode('utf-8')
            else:
                await ctx.send('Usage: `[p]base32 <encode|decode> <text>`')
                return
            await ctx.send(result)
        except (binascii.Error, ValueError, UnicodeDecodeError):
            await ctx.send('Invalid base32 string.')

    @staticmethod
    def _base36_encode(data: str) -> str:
        num = int.from_bytes(data.encode('utf-8'), 'big')
        if num == 0:
            return '0'
        result = []
        while num > 0:
            num, rem = divmod(num, 36)
            result.append(EncodingCommands.BASE36_ALPHABET[rem])
        return ''.join(reversed(result))

    @staticmethod
    def _base36_decode(data: str) -> str:
        num = 0
        for char in data.lower():
            if char not in EncodingCommands.BASE36_ALPHABET:
                raise ValueError('Invalid base36 character')
            num = num * 36 + EncodingCommands.BASE36_ALPHABET.index(char)
        byte_len = (num.bit_length() + 7) // 8
        return num.to_bytes(byte_len, 'big').decode('utf-8', errors='replace')

    @commands.command()
    async def base36(self, ctx, mode: str, *, text: str):
        await self._delete_invoke(ctx)
        mode = self._normalize_mode(mode)
        try:
            if mode == 'encode':
                result = self._base36_encode(text)
            elif mode == 'decode':
                result = self._base36_decode(text)
            else:
                await ctx.send('Usage: `[p]base36 <encode|decode> <text>`')
                return
            await ctx.send(result)
        except (ValueError, UnicodeDecodeError):
            await ctx.send('Invalid base36 string.')

    @staticmethod
    def _base58_encode(data: str) -> str:
        num = int.from_bytes(data.encode('utf-8'), 'big')
        if num == 0:
            return EncodingCommands.BASE58_ALPHABET[0]
        result = []
        while num > 0:
            num, rem = divmod(num, 58)
            result.append(EncodingCommands.BASE58_ALPHABET[rem])
        for byte in data.encode('utf-8'):
            if byte == 0:
                result.append(EncodingCommands.BASE58_ALPHABET[0])
            else:
                break
        return ''.join(reversed(result))

    @staticmethod
    def _base58_decode(data: str) -> str:
        num = 0
        for char in data:
            if char not in EncodingCommands.BASE58_ALPHABET:
                raise ValueError('Invalid base58 character')
            num = num * 58 + EncodingCommands.BASE58_ALPHABET.index(char)
        byte_len = (num.bit_length() + 7) // 8
        return num.to_bytes(byte_len, 'big').decode('utf-8', errors='replace')

    @commands.command()
    async def base58(self, ctx, mode: str, *, text: str):
        await self._delete_invoke(ctx)
        mode = self._normalize_mode(mode)
        try:
            if mode == 'encode':
                result = self._base58_encode(text)
            elif mode == 'decode':
                result = self._base58_decode(text)
            else:
                await ctx.send('Usage: `[p]base58 <encode|decode> <text>`')
                return
            await ctx.send(result)
        except (ValueError, UnicodeDecodeError):
            await ctx.send('Invalid base58 string.')

    @commands.command()
    async def base64(self, ctx, mode: str, *, text: str):
        await self._delete_invoke(ctx)
        mode = self._normalize_mode(mode)
        try:
            if mode == 'encode':
                result = base64.b64encode(text.encode('utf-8')).decode('utf-8')
            elif mode == 'decode':
                padded = text + '=' * (4 - len(text) % 4) if len(text) % 4 else text
                result = base64.b64decode(padded.encode('utf-8')).decode('utf-8')
            else:
                await ctx.send('Usage: `[p]base64 <encode|decode> <text>`')
                return
            await ctx.send(result)
        except (binascii.Error, ValueError, UnicodeDecodeError):
            await ctx.send('Invalid base64 string.')

    @commands.command()
    async def base64url(self, ctx, mode: str, *, text: str):
        await self._delete_invoke(ctx)
        mode = self._normalize_mode(mode)
        try:
            if mode == 'encode':
                result = base64.urlsafe_b64encode(text.encode('utf-8')).decode('utf-8').rstrip('=')
            elif mode == 'decode':
                padded = text + '=' * (4 - len(text) % 4) if len(text) % 4 else text
                padded = padded.replace('-', '+').replace('_', '/')
                result = base64.b64decode(padded.encode('utf-8')).decode('utf-8')
            else:
                await ctx.send('Usage: `[p]base64url <encode|decode> <text>`')
                return
            await ctx.send(result)
        except (binascii.Error, ValueError, UnicodeDecodeError):
            await ctx.send('Invalid base64url string.')

    @commands.command()
    async def ascii85(self, ctx, mode: str, *, text: str):
        await self._delete_invoke(ctx)
        mode = self._normalize_mode(mode)
        try:
            if mode == 'encode':
                result = base64.a85encode(text.encode('utf-8')).decode('utf-8')
            elif mode == 'decode':
                result = base64.a85decode(text.encode('utf-8')).decode('utf-8')
            else:
                await ctx.send('Usage: `[p]ascii85 <encode|decode> <text>`')
                return
            await ctx.send(result)
        except (binascii.Error, ValueError, UnicodeDecodeError):
            await ctx.send('Invalid ascii85 string.')

    @commands.command()
    async def base85(self, ctx, mode: str, *, text: str):
        await self._delete_invoke(ctx)
        mode = self._normalize_mode(mode)
        try:
            if mode == 'encode':
                result = base64.b85encode(text.encode('utf-8')).decode('utf-8')
            elif mode == 'decode':
                result = base64.b85decode(text.encode('utf-8')).decode('utf-8')
            else:
                await ctx.send('Usage: `[p]base85 <encode|decode> <text>`')
                return
            await ctx.send(result)
        except (binascii.Error, ValueError, UnicodeDecodeError):
            await ctx.send('Invalid base85 string.')

    @commands.command()
    async def urlencode(self, ctx, mode: str, *, text: str):
        await self._delete_invoke(ctx)
        mode = self._normalize_mode(mode)
        try:
            if mode == 'encode':
                result = urllib.parse.quote(text, safe='')
            elif mode == 'decode':
                result = urllib.parse.unquote(text)
            else:
                await ctx.send('Usage: `[p]urlencode <encode|decode> <text>`')
                return
            await ctx.send(result)
        except (ValueError,):
            await ctx.send('Invalid URL-encoded string.')

    @commands.command()
    async def morsecode(self, ctx, mode: str, *, text: str):
        await self._delete_invoke(ctx)
        mode = self._normalize_mode(mode)
        try:
            if mode == 'encode':
                result = ' '.join(self.MORSE_ENCODE.get(c.upper(), '?') for c in text)
            elif mode == 'decode':
                result = ''.join(self.MORSE_DECODE.get(code, '?') for code in text.split()).replace('/', ' ')
            else:
                await ctx.send('Usage: `[p]morsecode <encode|decode> <text>`')
                return
            await ctx.send(result)
        except Exception:
            await ctx.send('Invalid morse code string.')

    @commands.command()
    async def md5(self, ctx, *, text: str):
        await self._delete_invoke(ctx)
        result = hashlib.md5(text.encode('utf-8')).hexdigest()
        await ctx.send(result)

    @commands.command()
    async def sha1(self, ctx, *, text: str):
        await self._delete_invoke(ctx)
        result = hashlib.sha1(text.encode('utf-8')).hexdigest()
        await ctx.send(result)

    @commands.command()
    async def sha224(self, ctx, *, text: str):
        await self._delete_invoke(ctx)
        result = hashlib.sha224(text.encode('utf-8')).hexdigest()
        await ctx.send(result)

    @commands.command()
    async def sha256(self, ctx, *, text: str):
        await self._delete_invoke(ctx)
        result = hashlib.sha256(text.encode('utf-8')).hexdigest()
        await ctx.send(result)

    @commands.command()
    async def sha384(self, ctx, *, text: str):
        await self._delete_invoke(ctx)
        result = hashlib.sha384(text.encode('utf-8')).hexdigest()
        await ctx.send(result)

    @commands.command()
    async def sha512(self, ctx, *, text: str):
        await self._delete_invoke(ctx)
        result = hashlib.sha512(text.encode('utf-8')).hexdigest()
        await ctx.send(result)

    @commands.command()
    async def blake2b(self, ctx, *, text: str):
        await self._delete_invoke(ctx)
        result = hashlib.blake2b(text.encode('utf-8')).hexdigest()
        await ctx.send(result)

    @commands.command()
    async def blake2s(self, ctx, *, text: str):
        await self._delete_invoke(ctx)
        result = hashlib.blake2s(text.encode('utf-8')).hexdigest()
        await ctx.send(result)

    @commands.command()
    async def adler32(self, ctx, *, text: str):
        await self._delete_invoke(ctx)
        result = hex(zlib.adler32(text.encode('utf-8')))
        await ctx.send(result)

    @commands.command()
    async def crc32(self, ctx, *, text: str):
        await self._delete_invoke(ctx)
        result = hex(zlib.crc32(text.encode('utf-8')) & 0xFFFFFFFF)
        await ctx.send(result)

    @staticmethod
    def _crc64(data: bytes) -> int:
        crc = 0xFFFFFFFFFFFFFFFF
        for byte in data:
            crc = EncodingCommands.CRC64_TABLE[(crc ^ byte) & 0xFF] ^ (crc >> 8)
        return crc ^ 0xFFFFFFFFFFFFFFFF

    @commands.command()
    async def crc64(self, ctx, *, text: str):
        await self._delete_invoke(ctx)
        result = hex(self._crc64(text.encode('utf-8')))
        await ctx.send(result)

    @staticmethod
    def _fnv32(data: bytes) -> int:
        h = EncodingCommands.FNV_32_OFFSET
        for byte in data:
            h ^= byte
            h = (h * EncodingCommands.FNV_32_PRIME) & 0xFFFFFFFF
        return h

    @commands.command()
    async def fnv32(self, ctx, *, text: str):
        await self._delete_invoke(ctx)
        result = hex(self._fnv32(text.encode('utf-8')))
        await ctx.send(result)

    @staticmethod
    def _fnv64(data: bytes) -> int:
        h = EncodingCommands.FNV_64_OFFSET
        for byte in data:
            h ^= byte
            h = (h * EncodingCommands.FNV_64_PRIME) & 0xFFFFFFFFFFFFFFFF
        return h

    @commands.command()
    async def fnv64(self, ctx, *, text: str):
        await self._delete_invoke(ctx)
        result = hex(self._fnv64(text.encode('utf-8')))
        await ctx.send(result)

    @staticmethod
    def _fnv128(data: bytes) -> int:
        h = EncodingCommands.FNV_128_OFFSET
        for byte in data:
            h ^= byte
            h = (h * EncodingCommands.FNV_128_PRIME) & 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
        return h

    @commands.command()
    async def fnv128(self, ctx, *, text: str):
        await self._delete_invoke(ctx)
        result = hex(self._fnv128(text.encode('utf-8')))
        await ctx.send(result)

    @staticmethod
    def _aes_encrypt(key: str, text: str, key_size: int):
        key_bytes = key.encode('utf-8')
        if len(key_bytes) != key_size:
            raise ValueError(f'AES-{key_size * 8} requires a {key_size}-byte key. Your key is {len(key_bytes)} bytes.')
        cipher = AES.new(key_bytes, AES.MODE_CBC)
        iv = cipher.iv
        ciphertext = cipher.encrypt(pad(text.encode('utf-8'), AES.block_size))
        return base64.b64encode(iv + ciphertext).decode('utf-8')

    @staticmethod
    def _aes_decrypt(key: str, text: str, key_size: int):
        key_bytes = key.encode('utf-8')
        if len(key_bytes) != key_size:
            raise ValueError(f'AES-{key_size * 8} requires a {key_size}-byte key. Your key is {len(key_bytes)} bytes.')
        raw = base64.b64decode(text.encode('utf-8'))
        iv = raw[:16]
        ciphertext = raw[16:]
        cipher = AES.new(key_bytes, AES.MODE_CBC, iv=iv)
        plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)
        return plaintext.decode('utf-8')

    def _parse_aes_args(self, ctx):
        args = self._parse_quoted_args(ctx.message.content)
        if len(args) != 2:
            return None, None
        return args[0], args[1]

    @commands.command()
    async def aes128(self, ctx, mode: str):
        if not PYCRYPTODOME_AVAILABLE:
            await self._delete_invoke(ctx)
            await ctx.send('pycryptodome is not installed. Run `pip install pycryptodome`.')
            return
        await self._delete_invoke(ctx)
        mode = self._normalize_mode(mode)
        key, text = self._parse_aes_args(ctx)
        if key is None:
            await ctx.send('Usage: `[p]aes128 <encrypt/decrypt> "key" "text"`')
            return
        try:
            if mode == 'encrypt':
                result = self._aes_encrypt(key, text, 16)
            elif mode == 'decrypt':
                result = self._aes_decrypt(key, text, 16)
            else:
                await ctx.send('Usage: `[p]aes128 <encrypt/decrypt> "key" "text"`')
                return
            await ctx.send(result)
        except (ValueError, binascii.Error, UnicodeDecodeError):
            await ctx.send('Decryption failed. Check your key and ciphertext.')
        except Exception:
            await ctx.send('Decryption failed. Check your key and ciphertext.')

    @commands.command()
    async def aes192(self, ctx, mode: str):
        if not PYCRYPTODOME_AVAILABLE:
            await self._delete_invoke(ctx)
            await ctx.send('pycryptodome is not installed. Run `pip install pycryptodome`.')
            return
        await self._delete_invoke(ctx)
        mode = self._normalize_mode(mode)
        key, text = self._parse_aes_args(ctx)
        if key is None:
            await ctx.send('Usage: `[p]aes192 <encrypt/decrypt> "key" "text"`')
            return
        try:
            if mode == 'encrypt':
                result = self._aes_encrypt(key, text, 24)
            elif mode == 'decrypt':
                result = self._aes_decrypt(key, text, 24)
            else:
                await ctx.send('Usage: `[p]aes192 <encrypt/decrypt> "key" "text"`')
                return
            await ctx.send(result)
        except (ValueError, binascii.Error, UnicodeDecodeError):
            await ctx.send('Decryption failed. Check your key and ciphertext.')
        except Exception:
            await ctx.send('Decryption failed. Check your key and ciphertext.')

    @commands.command()
    async def aes256(self, ctx, mode: str):
        if not PYCRYPTODOME_AVAILABLE:
            await self._delete_invoke(ctx)
            await ctx.send('pycryptodome is not installed. Run `pip install pycryptodome`.')
            return
        await self._delete_invoke(ctx)
        mode = self._normalize_mode(mode)
        key, text = self._parse_aes_args(ctx)
        if key is None:
            await ctx.send('Usage: `[p]aes256 <encrypt/decrypt> "key" "text"`')
            return
        try:
            if mode == 'encrypt':
                result = self._aes_encrypt(key, text, 32)
            elif mode == 'decrypt':
                result = self._aes_decrypt(key, text, 32)
            else:
                await ctx.send('Usage: `[p]aes256 <encrypt/decrypt> "key" "text"`')
                return
            await ctx.send(result)
        except (ValueError, binascii.Error, UnicodeDecodeError):
            await ctx.send('Decryption failed. Check your key and ciphertext.')
        except Exception:
            await ctx.send('Decryption failed. Check your key and ciphertext.')


async def setup(bot):
    await bot.add_cog(EncodingCommands(bot))
