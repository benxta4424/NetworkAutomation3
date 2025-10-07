import asyncio
import re
import time
import requests
from scripts.backend.telnet_con import TelnetConnection
try:
    from scripts.backend.swagger_con import SwaggerConnector
except ImportError:
    SwaggerConnector = None

class FtdFullProvisioner:
    def __init__(
        self,
        host,
        port,
        username,
        initial_password,
        new_password,
        mgmt_ip,
        netmask,
        gateway,
        dns_server="8.8.8.8",
        mgmt_interface="Management1/1",
        swagger_port=443,
        ftd_device=None,  # pyATS device object for SwaggerConnector
        debug=True,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.initial_password = initial_password
        self.new_password = new_password
        self.mgmt_ip = mgmt_ip
        self.netmask = netmask
        self.gateway = gateway
        self.dns_server = dns_server
        self.mgmt_interface = mgmt_interface
        self.swagger_port = swagger_port
        self.ftd_device = ftd_device
        self.debug = debug
        self.conn = None

    async def wait_for_prompt(self, prompt, timeout=30):
        buffer = ""
        end_time = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < end_time:
            chunk = await self.conn.reader.read(8192)
            if chunk:
                buffer += chunk
                if self.debug:
                    print(chunk, end="")
                if re.search(prompt, buffer, re.IGNORECASE):
                    return buffer
            await asyncio.sleep(0.5)
        raise TimeoutError(f"Timeout waiting for prompt: {prompt}")

    async def send_and_wait(self, value, prompt, sleep=1, timeout=30):
        await self.conn.writeln(value)
        await asyncio.sleep(sleep)
        return await self.wait_for_prompt(prompt, timeout=timeout)

    async def cli_setup(self):
        print("Running FTD CLI setup...")
        self.conn = TelnetConnection(self.host, self.port)
        await self.conn.connect()
        try:
            await self.wait_for_prompt(r"(login:|username:)", timeout=60)
            await self.conn.writeln(self.username)
            await self.wait_for_prompt(r"password:", timeout=20)
            await self.conn.writeln(self.initial_password)
            buffer = await self.wait_for_prompt(r"(EULA|new password|password for admin|Press <ENTER>)", timeout=30)
            if "EULA" in buffer or "Press <ENTER>" in buffer:
                await self.conn.writeln("")
                await self.wait_for_prompt(r"YES|AGREE", timeout=30)
                await self.conn.writeln("YES")
                buffer = await self.wait_for_prompt(r"new password|password for admin", timeout=30)
            await self.conn.writeln(self.new_password)
            await self.wait_for_prompt(r"confirm|re-enter|retype|verify|again", timeout=20)
            await self.conn.writeln(self.new_password)
            await self.wait_for_prompt(r"configure IPv4", timeout=20)
            await self.conn.writeln("y")
            await self.wait_for_prompt(r"configure IPv6", timeout=20)
            await self.conn.writeln("n")
            await self.wait_for_prompt(r"dhcp/manual", timeout=20)
            await self.conn.writeln("manual")
            await self.wait_for_prompt(r"IPv4 address", timeout=20)
            await self.conn.writeln(self.mgmt_ip)
            await self.wait_for_prompt(r"netmask", timeout=20)
            await self.conn.writeln(self.netmask)
            await self.wait_for_prompt(r"default gateway", timeout=20)
            await self.conn.writeln(self.gateway)
            await self.wait_for_prompt(r"DNS servers", timeout=20)
            await self.conn.writeln(self.dns_server)
            await self.wait_for_prompt(r"search domains", timeout=20)
            await self.conn.writeln("")
            await self.wait_for_prompt(r"locally", timeout=20)
            await self.conn.writeln("yes")
            await self.wait_for_prompt(r"apply this configuration", timeout=30)
            await self.conn.writeln("y")
            await self.wait_for_prompt(r"firepower[#>]", timeout=120)
            await self.conn.writeln("show network")
            output = await self.wait_for_prompt(r"firepower[#>]", timeout=20)
            if self.mgmt_ip in output:
                print(f"✓ Management interface {self.mgmt_interface} configured with IP {self.mgmt_ip}")
                return True
            else:
                print(f"✗ Management interface {self.mgmt_interface} NOT configured correctly!")
                print(output)
                return False
        finally:
            await self.conn.close()

    def wait_for_api(self, timeout=300):
        print("Waiting for FTD API to become available...")
        start = time.time()
        while time.time() - start < timeout:
            try:
                r = requests.get(
                    f"https://{self.mgmt_ip}:{self.swagger_port}/api/versions",
                    verify=False,
                    timeout=5,
                )
                if r.status_code in (200, 401, 403):
                    print("✓ FTD API is available.")
                    return True
            except Exception:
                pass
            print(".", end="", flush=True)
            time.sleep(5)
        print("\n✗ FTD API did not become available in time.")
        return False

    def api_configure(self):
        if not self.ftd_device or not SwaggerConnector:
            print("No FTD device object provided for API configuration or SwaggerConnector not available.")
            return False
        connector = SwaggerConnector(self.ftd_device)
        connector.connect()
        client = connector.get_swagger_client()
        try:
            print("Configuring FTD interfaces via API...")
            existing_interfaces = client.Interface.getPhysicalInterfaceList().result()
            for interface in existing_interfaces.items:
                if hasattr(interface, "hardwareName") and interface.hardwareName in self.ftd_device.interfaces:
                    target_intf = self.ftd_device.interfaces[interface.hardwareName]
                    body = {
                        "id": interface.id,
                        "version": interface.version,
                        "name": getattr(interface, 'name', interface.hardwareName),
                        "hardwareName": interface.hardwareName,
                        "type": interface.type,
                        "mode": "ROUTED",
                        "enabled": True,
                        "managementOnly": False,
                        "monitorInterface": False,
                        "mtu": 1500,
                        "linkState": "UP",
                        "ipv4": {
                            "type": "interfaceipv4",
                            "ipType": "STATIC",
                            "dhcp": False,
                            "ipAddress": {
                                "type": "haipv4address",
                                "ipAddress": target_intf.ipv4.ip.compressed,
                                "netmask": target_intf.ipv4.netmask.exploded
                            }
                        },
                        "securityLevel": 50,
                        "description": f"Configured for {target_intf.ipv4.ip.compressed}/{target_intf.ipv4.netmask.exploded}"
                    }
                    client.Interface.editPhysicalInterface(objId=interface.id, body=body).result()
                    print(f"✓ Configured {interface.hardwareName}")
            print("Configuring default gateway...")
            network_model = client.get_model('Network')
            gateway_network = network_model(
                name="default_gateway",
                value=self.gateway + "/32",
                type="network"
            )
            gateway_network = client.Network.addNetwork(body=gateway_network).result()
            route_body = {
                "type": "staticroute",
                "gateway": {
                    "id": gateway_network.id,
                    "type": "network"
                },
                "metricValue": 1,
                "selectedNetworks": [
                    {
                        "type": "network",
                        "id": "any-ipv4",
                        "name": "any-ipv4"
                    }
                ]
            }
            client.Routing.addStaticRouteEntry(body=route_body).result()
            print("✓ Default gateway configured.")
            print("Deploying configuration...")
            deployment_body = {
                "type": "deploymentrequest",
                "forceDeploy": True,
                "ignoreWarning": True,
            }
            client.Deployment.addDeployment(body=deployment_body).result()
            print("✓ Deployment initiated.")
            return True
        except Exception as e:
            print(f"✗ API configuration failed: {e}")
            return False

    async def run(self):
        print("=== FTD CLI Initial Setup ===")
        cli_ok = await self.cli_setup()
        if not cli_ok:
            print("FTD CLI setup failed.")
            return False
        print("=== Waiting for FTD API ===")
        if not self.wait_for_api():
            print("FTD API not available.")
            return False
        print("=== FTD API Configuration ===")
        api_ok = self.api_configure()
        if not api_ok:
            print("FTD API configuration failed.")
            return False
        print("=== FTD Provisioning Complete ===")
        return True

# Main entry point for direct execution
if __name__ == "__main__":
    async def main():
        print("Starting FTD provisioning...")
        # Replace this with your actual pyATS device object for FTD if available
        ftd_device = None  # e.g., testbed.devices['FTD']
        provisioner = FtdFullProvisioner(
            host="92.81.55.146",
            port=5011,
            username="admin",
            initial_password="Admin123",
            new_password="Cisco@135",
            mgmt_ip="192.168.200.4",
            netmask="255.255.255.0",
            gateway="192.168.200.1",
            dns_server="192.168.200.1",
            mgmt_interface="Management1/1",
            swagger_port=443,
            ftd_device=ftd_device,
            debug=True,
        )
        result = await provisioner.run()
        if result:
            print("FTD full provisioning succeeded.")
        else:
            print("FTD full provisioning failed.")

    import sys
    if sys.version_info >= (3, 7):
        asyncio.run(main())
    else:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())