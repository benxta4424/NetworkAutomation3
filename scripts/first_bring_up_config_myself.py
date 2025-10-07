import asyncio
import time

from netmiko.cli_tools.helpers import ssh_conn
from pyats import aetest, topology
import subprocess

from scripts.telnet_con import TelnetConnection
from scripts.commands import commands


class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def load_bed(self, steps):
        with steps.start("Loading the testbed:"):
            self.testBed = topology.loader.load("copie_testbed1.yaml")
            self.parent.parameters.update(testBed = self.testBed)


    @aetest.subsection
    def bring_server_up(self, steps):
        server = self.testBed.devices["UbuntuServer"]
        with steps.start("Bring up server interface"):
            for interface_name, interface in server.interfaces.items():
                subprocess.run(["sudo", "ip", "address", "add", f"{interface.ipv4}", "dev" ,interface_name])
                subprocess.run(["sudo", "ip", "link", "set", interface_name, "up"])

        with steps.start("Add routes"):
            for device in self.testBed.devices:
                if self.testBed.devices[device].type != "router":
                    continue
                gateway_current_device = self.testBed.devices[device].interfaces["initial"].ipv4.compressed

                for interface in self.testBed.devices[device].interfaces:
                    if self.testBed.devices[device].interfaces[interface].link == "management":
                        continue
                    saved_ip = self.testBed.devices[device].interfaces[interface].ipv4.compressed
                    subprocess.run(["ip", "route", "add", saved_ip, "via", gateway_current_device])
        time.sleep(2)

    @aetest.subsection
    def bring_up_interfaces(self, steps):
        for device in self.testBed.devices:
            if self.testBed.devices[device].type != "router":
                continue

            with steps.start(f"Bring up interfaces for: ---{self.testBed.devices[device]}"):
                for dev_interface in self.testBed.devices[device].interfaces:
                    if self.testBed.devices[device].interfaces[dev_interface].link.name == "management":
                        continue

                    dev_object = self.testBed.devices[device].interfaces[dev_interface]
                    connection_host = self.testBed.devices[device].connections.telnet.ip.compressed
                    connection_port = self.testBed.devices[device].connections.telnet.port

                    get_commands = commands
                    conn_class = self.testBed.devices[device].connections.get("telnet", {}).get("class", None)

#                     we then get the commandsd

                    formatted_commands = list(
                        map(
                            lambda line:
                                line.format(
                                    interface = dev_interface,
                                    ip = dev_object.ipv4.ip.compressed,
                                    sm = dev_object.ipv4.netmask.exploded,
                                    hostname = device,
                                    domain = self.testBed.devices[device].custom.get("domain", ""),
                                    username = self.testBed.devices[device].credentials.default.username,
                                    password = self.testBed.devices[device].credentials.default.password.plaintext
                                ), get_commands
                        )
                    )

                    conn: TelnetConnection = conn_class(connection_host, connection_port)

                    # after connecting to the device we run the script
                    async def setup():
                        await conn.connect()
                        time.sleep(1)
                        await conn.execute_commends(formatted_commands,"#")
                    asyncio.run(setup())



if __name__ == "__main__":
    aetest.main()