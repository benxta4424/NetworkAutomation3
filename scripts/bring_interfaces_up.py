import asyncio
import subprocess
import sys
import time

from pyats import aetest, topology

import modul12.commands as ssh_commands
from telnet_con import  TelnetConnection

print(sys.path)


class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def load_testbed(self, steps):
        with steps.start("Load testbed"):
            self.tb = topology.loader.load('copie_testbed1.yaml')
            self.parent.parameters.update(tb=self.tb)

    @aetest.subsection
    def bring_up_server_interface(self, steps):
        # tb = self.parent.parameters.get('tb')
        server = self.tb.devices['UbuntuServer']
        for intf_name, intf in server.interfaces.items():
            # intf = server.interfaces[interface]
            with steps.start(f'Bring up interface {intf_name}'):
                subprocess.run(['sudo', 'ip', 'addr', 'add', f'{intf.ipv4}', 'dev', f'{intf_name}'])
                subprocess.run(['sudo', 'ip', 'link', 'set', 'dev', f'{intf_name}', 'up'])

        with steps.start('Add routes'):
            for device in self.tb.devices:
                if self.tb.devices[device].type != 'router':
                    continue
                gateway = self.tb.devices[device].interfaces['initial'].ipv4.ip.compressed
                for interface in self.tb.devices[device].interfaces:
                    if self.tb.devices[device].interfaces[interface].link.name == 'management':
                        continue
                    subnet = self.tb.devices[device].interfaces[interface].ipv4.network.compressed
                    subprocess.run(['sudo', 'ip', 'route', 'add', f'{subnet}', 'via', f'{gateway}'])

        time.sleep(2)

    @aetest.subsection
    def bring_up_router_interface(self, steps):
        for device in self.tb.devices:
            if self.tb.devices[device].type != 'router':
                continue
            with steps.start(f'Bring up interface {device}', continue_=True):

                for interface in self.tb.devices[device].interfaces:
                    if self.tb.devices[device].interfaces[interface].link.name != 'management':
                        continue

                    intf_obj = self.tb.devices[device].interfaces[interface]
                    conn_class = self.tb.devices[device].connections.get('telnet', {}).get('class', None)
                    assert conn_class, 'No connection for device {}'.format(device)
                    ip = self.tb.devices[device].connections.telnet.ip.compressed
                    port = self.tb.devices[device].connections.telnet.port
                    commands = ssh_commands.commands
                    formatted_commands = list(map(
                        lambda s: s.format(
                            interface=interface,
                            ip=intf_obj.ipv4.ip.compressed,
                            sm=intf_obj.ipv4.netmask.exploded,
                            hostname=device,
                            domain=self.tb.devices[device].custom.get('domain', ''),
                            username=self.tb.devices[device].credentials.default.username,
                            password=self.tb.devices[device].credentials.default.password.plaintext,

                        ),
                        commands
                    ))

                    conn: TelnetConnection = conn_class(ip, port)

                    async def setup():
                        await conn.connect()
                        time.sleep(1)
                        await conn.execute_commends(formatted_commands, '#')

                    asyncio.run(setup())




class ConfigureInterfaces(aetest.Testcase):

    @aetest.setup
    def configure(self):
        tb = self.parent.parameters['tb']
        conn = tb.devices.IOU1.connections.telnet['class']
        print(conn)


if __name__ == '__main__':
    aetest.main()