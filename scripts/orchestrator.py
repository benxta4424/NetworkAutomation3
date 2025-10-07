import asyncio
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from pyats import topology
from scripts.telnet_con import TelnetConnection
from commands import device_commands, interface_commands


class NetworkOrchestrator:
    def __init__(self, test_bed="copie_testbed1.yaml"):
        self.test_bed = test_bed
        self.configured_passed = set()
        self.configured_failed = set()
        self.max_workers = 4
        self.lock = threading.Lock()


        self.server_routes = {
            "192.168.10.0/24": "192.168.200.1",
            "192.168.20.0/24": "192.168.200.1",
            "192.168.30.0/24": "192.168.200.2",
            "192.168.40.0/24": "192.168.200.3",
            "192.168.50.0/24": "192.168.200.4",
        }

    def load_testbed(self):
        try:
            self.test_bed = topology.loader.load("copie_testbed1.yaml")
            return True
        except Exception as e:
            print(f"Testbed load error: {e}")
            return False

    def server_interfaces(self):
        server = self.test_bed.devices["UbuntuServer"]
        for interface_name, interface in server.interfaces.items():
            subprocess.run(
                ["sudo", "ip", "address", "add", f"{interface.ipv4.compressed}", "dev", interface_name],
                capture_output=True
            )
            subprocess.run(
                ["sudo", "ip", "link", "set", interface_name, "up"],
                capture_output=True
            )
        return True

    def add_server_routes(self):
        for network, gateway in self.server_routes.items():
            res = subprocess.run(
                ["sudo", "ip", "route", "add", network, "via", gateway],
                capture_output=True,
                text=True
            )
            if res.returncode != 0 and "File exists" not in res.stderr:
                print(f"Route error: {res.stderr}")
                return False
        return True

    async def configure_single_router(self, device_name: str):
        """Configure a single router - runs in a thread"""
        try:
            device = self.test_bed.devices[device_name]
            all_interface_commands = []
            rip_networks = set()

            for interface_name, interface_object in device.interfaces.items():
                if interface_object.link.name == "management" or interface_object.alias == "initial":
                    continue

                all_interface_commands.extend([
                    cmds.format(
                        interface=interface_name,
                        ip=interface_object.ipv4.ip.compressed,
                        sm=interface_object.ipv4.netmask.exploded
                    )
                    for cmds in interface_commands
                ])
                rip_networks.add(str(interface_object.ipv4.network.network_address))

            dev_cmds = [
                cmds.format(
                    hostname=device_name,
                    domain="example.com",
                    username=device.credentials.default.username,
                    password=device.credentials.default.password.plaintext,
                )
                for cmds in device_commands
            ]

            all_rip_commands = [
                "router rip",
                "version 2",
                "no auto-summary",
            ]

            for rip_command in sorted(rip_networks):
                all_rip_commands.append(f"network {rip_command}")

            combine_all_commands = all_interface_commands + dev_cmds + all_rip_commands
            host = device.connections.telnet.ip.compressed
            port = device.connections.telnet.port
            conn = TelnetConnection(host, port)

            await conn.connect()
            await conn.write("\n")
            await conn.execute_commands(combine_all_commands)
            await conn.close()

            with self.lock:
                self.configured_passed.add(device_name)
                print(f"✓ {device_name} configured successfully")
            return True

        except Exception as e:
            print(f"✗ {device_name} configuration failed: {e}")
            self.configured_failed.add(device_name)
            return False


    async def configure_first_three_routers(self):
        """Configure all routers in parallel using threads"""
        try:
            router_names = [
                dev_name for dev_name, dev in self.test_bed.devices.items()
                if dev.type == "router"
            ]
            tasks = [self.configure_single_router(rtr_name) for rtr_name in router_names]
            await asyncio.gather(*tasks)



        except Exception as e:
            print(f"Router configuration failed: {e}")
            return False

    def configure_ftd(self):
        pass


    def magic_mock(self):
        pass

# Usage
if __name__ == "__main__":
    orchestrator = NetworkOrchestrator()

    if not orchestrator.load_testbed():
        print("Failed to load testbed")
        exit(1)

    print("Configuring server interfaces...")
    orchestrator.server_interfaces()

    print("\nConfiguring routers...")
    asyncio.run(orchestrator.configure_first_three_routers())

    print("\nAdding server routes...")
    orchestrator.add_server_routes()

    print("\nOrchestration complete!")