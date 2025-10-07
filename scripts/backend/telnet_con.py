import telnetlib3
import asyncio
import re


class TelnetConnection:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
        # Basic prompt regex for many devices (# or > at line end)
        self.prompt_regex = re.compile(r'[#>]\s*$')

    async def connect(self):
        """Open telnet connection and populate reader/writer"""
        self.reader, self.writer = await telnetlib3.open_connection(
            self.host, self.port, encoding='utf-8', connect_minwait=0.5
        )

    async def write(self, data: str):
        """Write data without automatic newline"""
        if self.writer is None:
            raise RuntimeError("Telnet writer not connected")
        if data is None:
            data = ""
        self.writer.write(data)
        await self.writer.drain()
        await asyncio.sleep(0.5)  # Give device time to process

    async def writeln(self, data: str):
        """Write data with newline"""
        if self.writer is None:
            raise RuntimeError("Telnet writer not connected")
        if data is None:
            data = ""
        self.writer.write(data + '\n')
        await self.writer.drain()
        await asyncio.sleep(0.3)

    async def readuntil(self, timeout: float = 10.0):
        """Read until timeout, returning all accumulated data"""
        buffer = ''
        end_time = asyncio.get_event_loop().time() + timeout

        try:
            while asyncio.get_event_loop().time() < end_time:
                remaining = end_time - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break

                try:
                    chunk = await asyncio.wait_for(self.reader.read(8192), timeout=min(remaining, 1.0))
                    if chunk:
                        buffer += chunk
                    else:
                        # No more data available
                        await asyncio.sleep(0.05)
                except asyncio.TimeoutError:
                    # No data in this interval, return if we have some
                    if buffer:
                        break
                    continue
        except Exception as e:
            print(f"Read error: {e}")

        return buffer

    async def read_until_prompt(self, prompt: str, timeout: float = 10.0):
        """Read until a specific prompt string appears"""
        buffer = ''
        end_time = asyncio.get_event_loop().time() + timeout

        try:
            while asyncio.get_event_loop().time() < end_time:
                remaining = end_time - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break

                try:
                    chunk = await asyncio.wait_for(self.reader.read(8192), timeout=min(remaining, 0.5))
                    if chunk:
                        buffer += chunk
                        if prompt in buffer:
                            return buffer
                except asyncio.TimeoutError:
                    if prompt in buffer:
                        return buffer
                    continue
        except Exception as e:
            print(f"Read error: {e}")

        return buffer

    async def execute_commands(self, commands: list):
        for cmd in commands:
            await self.writeln(cmd)
            await asyncio.sleep(0.2)
            await self.wait_for_prompt(timeout=5)

    async def wait_for_prompt(self, timeout: float = 10.0):
        buffer = ''
        end_time = asyncio.get_event_loop().time() + timeout
        try:
            while asyncio.get_event_loop().time() < end_time:
                remaining = end_time - asyncio.get_event_loop().time()
                try:
                    chunk = await asyncio.wait_for(self.reader.read(8192), timeout=min(remaining, 1.0))
                    if chunk:
                        buffer += chunk
                        if self.prompt_regex.search(buffer):
                            return buffer
                    else:
                        await asyncio.sleep(0.05)
                except asyncio.TimeoutError:
                    if self.prompt_regex.search(buffer):
                        return buffer
                    continue
        except Exception as e:
            print(f"wait_for_prompt error: {e}")
        return buffer

    async def close(self):
        if self.writer:
            self.writer.close()
            if hasattr(self.writer, "wait_closed"):
                try:
                    await self.writer.wait_closed()
                except Exception:
                    pass