import asyncio
import re
import sys
import time

from pyats import aetest, topology
from pyats.aetest.steps import Step

from telnet_con import TelnetConnection

print(sys.path)


class ConfigureFDMManagement(aetest.Testcase):
    @aetest.test
    def load_testbed(self, steps):
        with steps.start("Load testbed"):
            self.tb = topology.loader.load('copie_testbed1.yaml')
            self.parent.parameters.update(tb=self.tb)

    @aetest.test
    def bring_up_router_interface(self, steps):
        for device in self.tb.devices:
            if self.tb.devices[device].type != 'ftd':
                continue
            with steps.start(f'Bring up management interface {device}', continue_=True) as step:  # type: Step

                for interface in self.tb.devices[device].interfaces:
                    if self.tb.devices[device].interfaces[interface].link.name != 'management':
                        continue

                    intf_obj = self.tb.devices[device].interfaces[interface]
                    conn_class = self.tb.devices[device].connections.get('telnet', {}).get('class', None)
                    assert conn_class, 'No connection for device {}'.format(device)
                    ip = self.tb.devices[device].connections.telnet.ip.compressed
                    port = self.tb.devices[device].connections.telnet.port
                    conn: TelnetConnection = conn_class(ip, port)

                    async def setup():
                        await conn.connect()
                        time.sleep(5)
                        conn.writer.write('\n')
                        time.sleep(5)
                        out = await conn.read(n=1000)
                        print(out)
                        result = re.search(r'^\s*(?P<login>firepower login:)', out)
                        if not result:
                            step.skipped(reason='Configuration not required')

                        if result.group('login'):
                            conn.writer.write('admin\n')
                            time.sleep(5)
                            conn.writer.write('Admin123\n')
                            time.sleep(5)

                        out = await conn.read(n=1000)
                        if 'EULA:' in out:
                            conn.writer.write('\n')

                            while True:
                                time.sleep(5)
                                out = await conn.read(n=1000)
                                if '--More--' in out:
                                    conn.writer.write(' ')
                                elif 'EULA:' in out:
                                    conn.writer.write('\n')
                                    time.sleep(5)
                                    out = await conn.read(n=1000)
                                    break
                                else:
                                    print('no str found in eula')

                        if 'password:' in out:
                            conn.writer.write(self.tb.devices[device].credentials.default.password.plaintext + '\n')
                            time.sleep(5)
                            out = await conn.read(n=1000)
                            if 'password:' in out:
                                conn.writer.write(self.tb.devices[device].credentials.default.password.plaintext + '\n')
                                time.sleep(5)
                                out = await conn.read(n=1000)

                        if 'IPv4? (y/n) [y]:' in out:
                            conn.writer.write('\n')
                            time.sleep(5)
                            out = await conn.read(n=1000)

                        if 'IPv6? (y/n) [n]:' in out:
                            conn.writer.write('\n')
                            time.sleep(5)
                            out = await conn.read(n=1000)

                        if '[manual]:' in out:
                            conn.writer.write('\n')
                            time.sleep(5)
                            out = await conn.read(n=1000)

                        if '[192.168.45.45]:' in out:
                            conn.writer.write(intf_obj.ipv4.ip.compressed + '\n')
                            time.sleep(5)
                            out = await conn.read(n=1000)

                        if '[255.255.255.0]:' in out:
                            conn.writer.write(intf_obj.ipv4.netmask.exploded + '\n')
                            time.sleep(5)
                            out = await conn.read(n=1000)

                        if '[192.168.45.1]:' in out:
                            conn.writer.write((intf_obj.ipv4.ip + 1).compressed + '\n')
                            time.sleep(5)
                            out = await conn.read(n=1000)

                        if '::35]:' in out:
                            conn.writer.write('\n')
                            time.sleep(5)
                            out = await conn.read(n=1000)

                        if "'none' []:" in out:
                            conn.writer.write('\n')
                            time.sleep(10)
                            out = await conn.read(n=1000)

                        if "locally? (yes/no) [yes]:" in out:
                            conn.writer.write('\n')
                            time.sleep(5)
                            out = await conn.read(n=1000)


                    asyncio.run(setup())



# class ConfigureInterfaces(aetest.Testcase):
#
#     @aetest.setup
#     def configure(self):
#         tb = self.parent.parameters['tb']
#         conn = tb.devices.IOU1.connections.telnet['class']
#         print(conn)


if __name__ == '__main__':
    aetest.main()