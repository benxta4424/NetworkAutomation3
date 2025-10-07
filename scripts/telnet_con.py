import telnetlib3
import asyncio
import re

class TelnetConnection:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
        self.prompt_regex = re.compile(r'[#>]\s*$')

    async def connect(self):
        self.reader, self.writer = await telnetlib3.open_connection(
            self.host, self.port, encoding='utf8'
        )

    async def write(self, data: str):
        self.writer.write(data + '\r\n')
        await self.writer.drain()  # ✅ must await

    async def readuntil(self, separator: str = '#', timeout: float = 5.0):
        """Read until the separator or timeout"""
        buffer = ''
        try:
            while True:
                chunk = await asyncio.wait_for(self.reader.read(1024), timeout)
                if chunk is None:
                    break
                buffer += chunk
                if separator in chunk:
                    break
        except asyncio.TimeoutError:
            pass
        return buffer

    async def execute_commands(self, commands: list):
        for cmd in commands:
            await self.write(cmd)
            await self.readuntil('#')

    async def close(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
