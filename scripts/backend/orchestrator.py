import asyncio
import subprocess
import threading
import time
import json
from typing import Dict, Optional
import requests
from pyats import topology
import re
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Local backend imports
from scripts.backend.telnet_con import TelnetConnection
from scripts.backend.swagger_con import SwaggerConnector
from scripts.backend.commands import device_commands, interface_commands


class NetworkOrchestrator:
    def __init__(self, test_bed: str = "copie_testbed1.yaml", status_callback=None):
        self.test_bed = test_bed
        self.test_bed_data = None
        self.configured_passed = set()
        self.configured_failed = set()
        self.max_workers = 4
        self.lock = threading.Lock()
        self.status_callback = status_callback
        self.server_routes = {
            "192.168.10.0/24": "192.168.200.1",
            "192.168.20.0/24": "192.168.200.1",
            "192.168.30.0/24": "192.168.200.2",
            "192.168.40.0/24": "192.168.200.3",
            "192.168.50.0/24": "192.168.200.4",
        }

    def _update_status(self, step_id: int, completed: bool = False, in_progress: bool = False, message: str = ""):
        """Thread-safe status update"""
        if self.status_callback:
            try:
                self.status_callback(step_id, completed, in_progress, message)
            except Exception as e:
                print(f"[STATUS CALLBACK ERROR] {e}")
        if message:
            print(f"[STATUS] Step {step_id}: {message}")

    def load_testbed(self) -> bool:
        """Load testbed YAML file"""
        try:
            self._update_status(1, in_progress=True, message="Loading testbed...")
            self.test_bed_data = topology.loader.load(self.test_bed)
            self._update_status(1, completed=True, message="Testbed loaded successfully")
            return True
        except Exception as e:
            self._update_status(1, completed=False, message=f"Testbed load error: {e}")
            print(f"[ERROR] Failed to load testbed: {e}")
            return False

    def server_interfaces(self) -> bool:
        """Configure server interfaces and routes"""
        try:
            self._update_status(2, in_progress=True, message="Configuring server interfaces...")
            server = self.test_bed_data.devices.get("UbuntuServer")
            if not server:
                self._update_status(2, completed=False, message="UbuntuServer not found in testbed")
                return False

            for interface_name, interface in server.interfaces.items():
                result = subprocess.run(
                    ["sudo", "ip", "address", "add", f"{interface.ipv4.compressed}", "dev", interface_name],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0 and "File exists" not in (result.stderr or ""):
                    print(f"Interface error on {interface_name}: {result.stderr}")

                subprocess.run(["sudo", "ip", "link", "set", interface_name, "up"], capture_output=True)

            self._update_status(2, in_progress=True, message="Adding server routes...")
            for network, gateway in self.server_routes.items():
                result = subprocess.run(
                    ["sudo", "ip", "route", "add", network, "via", gateway],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0 and "File exists" not in (result.stderr or ""):
                    print(f"Route error for {network}: {result.stderr}")

            self._update_status(2, completed=True, message="Server interfaces and routes configured")
            return True

        except Exception as e:
            self._update_status(2, completed=False, message=f"Server configuration failed: {e}")
            print(f"[ERROR] Server configuration failed: {e}")
            return False

    async def configure_single_router(self, device_name: str) -> bool:
        """Configure a single router with timeout protection"""
        try:
            device = self.test_bed_data.devices[device_name]
            all_interface_commands = []
            rip_networks = set()

            self._update_status(3, in_progress=True, message=f"Configuring {device_name}...")

            for interface_name, interface_object in device.interfaces.items():
                if getattr(interface_object.link, "name", "") == "management" or getattr(interface_object, "alias", "") == "initial":
                    continue

                all_interface_commands.extend([
                    cmds.format(
                        interface=interface_name,
                        ip=interface_object.ipv4.ip.compressed,
                        sm=interface_object.ipv4.netmask.compressed,
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

            all_rip_commands = ["router rip", "version 2", "no auto-summary"]
            for network in sorted(rip_networks):
                all_rip_commands.append(f"network {network}")

            combined_commands = all_interface_commands + dev_cmds + all_rip_commands

            host = device.connections.telnet.ip.compressed
            port = device.connections.telnet.port
            conn = TelnetConnection(host, port)
            await asyncio.wait_for(conn.connect(), timeout=30)

            try:
                await conn.writeln("")
                await asyncio.sleep(1)
                banner = await asyncio.wait_for(conn.readuntil(timeout=5), timeout=10)
                print(f"{device_name} connected: {banner[:100]}")

                for cmd in combined_commands:
                    try:
                        await conn.writeln(cmd)
                        out = await asyncio.wait_for(conn.readuntil(timeout=2), timeout=5)
                        print(f"{device_name} >> {cmd[:50]}")
                    except asyncio.TimeoutError:
                        print(f"{device_name} timeout on command: {cmd[:50]}")
                    except Exception as e:
                        print(f"{device_name} error on '{cmd[:50]}': {e}")

            finally:
                await conn.close()

            with self.lock:
                self.configured_passed.add(device_name)
            self._update_status(3, in_progress=True, message=f"{device_name} configured")
            print(f"✓ {device_name} configured successfully")
            return True

        except asyncio.TimeoutError:
            print(f"✗ {device_name} configuration timed out")
            with self.lock:
                self.configured_failed.add(device_name)
            self._update_status(3, in_progress=True, message=f"{device_name} timed out")
            return False

        except Exception as e:
            print(f"✗ {device_name} configuration failed: {e}")
            with self.lock:
                self.configured_failed.add(device_name)
            self._update_status(3, in_progress=True, message=f"{device_name} failed: {str(e)[:50]}")
            return False

    async def configure_routers(self) -> bool:
        """Configure all routers concurrently"""
        try:
            self._update_status(3, in_progress=True, message="Starting router configuration...")
            router_names = [dev_name for dev_name, dev in self.test_bed_data.devices.items() if getattr(dev, "type", "") == "router"]
            print(f"Found routers: {router_names}")

            if not router_names:
                self._update_status(3, completed=True, message="No routers to configure")
                return True

            tasks = [self.configure_single_router(router_name) for router_name in router_names]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            success_count = sum(1 for result in results if result is True)
            if success_count == len(router_names):
                self._update_status(3, completed=True, message=f"All {len(router_names)} routers configured")
                return True
            else:
                self._update_status(3, completed=False, message=f"Only {success_count}/{len(router_names)} routers configured")
                return False

        except Exception as e:
            self._update_status(3, completed=False, message=f"Router configuration failed: {e}")
            print(f"[ERROR] Router configuration failed: {e}")
            return False

    async def configure_ftd_initial_setup(self) -> bool:
        """Run FTD initial setup with hardcoded values for reliable command sending"""
        conn = None
        try:
            self._update_status(4, in_progress=True, message="Starting FTD initial setup...")
            host = "92.81.55.146"
            port = 5013
            username = "admin"
            initial_password = "Admin123"
            new_password = "Cisco@135"
            mgmt_ip = "192.168.200.4"
            netmask = "255.255.255.0"
            gateway = "192.168.200.1"
            dns_server = "192.168.200.1"

            print(f"Connecting to FTD at {host}:{port}")
            conn = TelnetConnection(host, port)
            await asyncio.wait_for(conn.connect(), timeout=30)

            try:
                print("FTD: Sending initial newline")
                await conn.writeln("")
                await asyncio.sleep(8)
                response = await asyncio.wait_for(conn.readuntil(timeout=15), timeout=20)
                print(f"FTD: Initial response: {response[:500]}")

                max_attempts = 30
                current_buffer = response
                login_attempts = 0
                max_login_attempts = 3
                setup_completed = False
                logged_in = False
                password_set = False

                for attempt in range(max_attempts):
                    try:
                        print(f"FTD attempt {attempt}: Buffer size {len(current_buffer)}")

                        if len(current_buffer.strip()) < 50:
                            try:
                                new_data = await asyncio.wait_for(conn.readuntil(timeout=8), timeout=10)
                                if new_data:
                                    current_buffer += new_data
                            except asyncio.TimeoutError:
                                pass

                        lower_buffer = current_buffer.lower()

                        if (
                            "firepower#" in current_buffer
                            or "firepower>" in current_buffer
                            or current_buffer.strip().endswith("> ")
                            or current_buffer.strip().endswith("# ")
                            or "welcome" in lower_buffer
                            or "configuration completed" in lower_buffer
                            or "configuration applied successfully" in lower_buffer
                            or "successfully performed firstboot" in lower_buffer
                        ):
                            print("FTD: Setup wizard completed!")
                            setup_completed = True
                            break

                        if not logged_in and ("login:" in lower_buffer or "username:" in lower_buffer):
                            if login_attempts >= max_login_attempts:
                                print("FTD: Too many login attempts")
                                break
                            print(f"FTD: Sending username (attempt {login_attempts + 1})")
                            await conn.writeln(username)
                            await asyncio.sleep(5)
                            current_buffer = await asyncio.wait_for(conn.readuntil(timeout=12), timeout=15)
                            continue

                        if not logged_in and "password:" in lower_buffer and login_attempts < max_login_attempts:
                            print(f"FTD: Sending initial factory password Admin123 (attempt {login_attempts + 1})")
                            await conn.writeln(initial_password)
                            login_attempts += 1
                            await asyncio.sleep(8)
                            current_buffer = await asyncio.wait_for(conn.readuntil(timeout=20), timeout=25)
                            if "login incorrect" not in current_buffer.lower():
                                logged_in = True
                                print("FTD: Successfully logged in with factory password!")
                            continue

                        if not logged_in and ("login incorrect" in lower_buffer or "authentication failed" in lower_buffer):
                            print(f"FTD: Login failed with factory password (attempt {login_attempts})")
                            if login_attempts >= max_login_attempts:
                                print("FTD: Trying with testbed password as fallback...")
                                await asyncio.sleep(5)
                                await conn.writeln(username)
                                await asyncio.sleep(3)
                                await conn.writeln(new_password)
                                await asyncio.sleep(8)
                                current_buffer = await asyncio.wait_for(conn.readuntil(timeout=20), timeout=25)
                                logged_in = True
                            continue

                        if logged_in and (
                            "end user license" in lower_buffer
                            or "eula" in lower_buffer
                            or "please enter" in lower_buffer
                            or "press <enter>" in lower_buffer
                        ):
                            print("FTD: Handling EULA")
                            for page in range(25):
                                await conn.writeln("")
                                await asyncio.sleep(1.5)
                                eula_response = await asyncio.wait_for(conn.readuntil(timeout=5), timeout=8)
                                current_buffer += eula_response
                                if "yes" in eula_response.lower() or "no" in eula_response.lower():
                                    print(f"FTD: Found EULA acceptance prompt after {page} pages")
                                    break
                            print("FTD: Accepting EULA")
                            await conn.writeln("YES")
                            await asyncio.sleep(8)
                            current_buffer = await asyncio.wait_for(conn.readuntil(timeout=15), timeout=20)
                            continue

                        if logged_in and not password_set and (
                            "enter new password" in lower_buffer
                            or "new password:" in lower_buffer
                            or "password for admin" in lower_buffer
                        ):
                            print(f"FTD: Setting new admin password to {new_password}")
                            await conn.writeln(new_password)
                            await asyncio.sleep(5)
                            current_buffer = await asyncio.wait_for(conn.readuntil(timeout=12), timeout=18)
                            continue

                        if logged_in and not password_set and (
                            ("confirm" in lower_buffer and "password" in lower_buffer)
                            or ("re-enter" in lower_buffer and "password" in lower_buffer)
                            or ("retype" in lower_buffer)
                            or ("verify" in lower_buffer and "password" in lower_buffer)
                            or ("enter password again" in lower_buffer)
                        ):
                            print(f"FTD: Confirming password with {new_password}")
                            await conn.writeln(new_password)
                            password_set = True
                            await asyncio.sleep(6)
                            current_buffer = await asyncio.wait_for(conn.readuntil(timeout=15), timeout=20)
                            continue

                        if logged_in and "password" in lower_buffer and ("not match" in lower_buffer or "mismatch" in lower_buffer):
                            print("FTD: Password mismatch detected, retrying...")
                            password_set = False
                            await asyncio.sleep(3)
                            current_buffer = await asyncio.wait_for(conn.readuntil(timeout=10), timeout=15)
                            continue

                        if logged_in and ("configure ipv4 via dhcp" in lower_buffer or "dhcp/manual" in lower_buffer):
                            print("FTD: Declining DHCP, choosing manual")
                            await conn.writeln("manual")
                            await asyncio.sleep(3)
                            current_buffer = await asyncio.wait_for(conn.readuntil(timeout=8), timeout=12)
                            continue

                        if logged_in and "ipv4 address" in lower_buffer and "management" in lower_buffer:
                            print(f"FTD: Setting IP address: {mgmt_ip}")
                            await conn.writeln(mgmt_ip)
                            await asyncio.sleep(3)
                            current_buffer = await asyncio.wait_for(conn.readuntil(timeout=8), timeout=12)
                            continue

                        if logged_in and "netmask" in lower_buffer and "management" in lower_buffer:
                            print(f"FTD: Setting netmask: {netmask}")
                            await conn.writeln(netmask)
                            await asyncio.sleep(3)
                            current_buffer = await asyncio.wait_for(conn.readuntil(timeout=8), timeout=12)
                            continue

                        if logged_in and "default gateway" in lower_buffer and "management" in lower_buffer:
                            print(f"FTD: Setting gateway: {gateway}")
                            await conn.writeln(gateway)
                            await asyncio.sleep(3)
                            current_buffer = await asyncio.wait_for(conn.readuntil(timeout=8), timeout=12)
                            continue

                        if logged_in and "dns server" in lower_buffer:
                            print(f"FTD: Setting DNS: {dns_server}")
                            await conn.writeln(dns_server)
                            await asyncio.sleep(5)
                            current_buffer = await asyncio.wait_for(conn.readuntil(timeout=12), timeout=18)
                            continue

                        if logged_in and "configure time" in lower_buffer:
                            print("FTD: Declining time configuration")
                            await conn.writeln("n")
                            await asyncio.sleep(3)
                            current_buffer = await asyncio.wait_for(conn.readuntil(timeout=8), timeout=12)
                            continue

                        if logged_in and "firepower management center" in lower_buffer:
                            print("FTD: Declining management center")
                            await conn.writeln("n")
                            await asyncio.sleep(3)
                            current_buffer = await asyncio.wait_for(conn.readuntil(timeout=8), timeout=12)
                            continue

                        if logged_in and "apply this configuration" in lower_buffer:
                            print("FTD: Applying configuration")
                            await conn.writeln("y")
                            await asyncio.sleep(10)
                            current_buffer = await asyncio.wait_for(conn.readuntil(timeout=20), timeout=30)
                            continue

                        print(f"FTD: No pattern match, checking for CLI prompt in: '{current_buffer[-20:]}'")
                        await asyncio.sleep(3)
                        try:
                            new_data = await asyncio.wait_for(conn.readuntil(timeout=5), timeout=8)
                            if new_data:
                                current_buffer += new_data
                            else:
                                await conn.writeln("")
                                await asyncio.sleep(2)
                                current_buffer = await asyncio.wait_for(conn.readuntil(timeout=5), timeout=8)
                        except asyncio.TimeoutError:
                            await conn.writeln("")
                            await asyncio.sleep(2)
                            current_buffer = await asyncio.wait_for(conn.readuntil(timeout=3), timeout=5)

                    except asyncio.TimeoutError:
                        print(f"FTD: Timeout in attempt {attempt}")
                        await asyncio.sleep(3)
                        continue
                    except Exception as e:
                        print(f"FTD: Error in attempt {attempt}: {e}")
                        await asyncio.sleep(3)
                        continue

                if setup_completed:
                    print("FTD: Setup wizard completed successfully")
                    self._update_status(4, completed=True, message="FTD initial setup completed")
                    return True
                else:
                    print("FTD: Setup wizard did not complete in time")
                    self._update_status(4, completed=False, message="FTD setup timed out")
                    return False

            finally:
                if conn:
                    await conn.close()

        except asyncio.TimeoutError:
            self._update_status(4, completed=False, message="FTD setup timed out")
            print("FTD: Setup timed out")
            return False
        except Exception as e:
            self._update_status(4, completed=False, message=f"FTD setup failed: {e}")
            print(f"[ERROR] FTD initial setup error: {e}")
            import traceback
            traceback.print_exc()
            return False
    def wait_for_fdm(self, ip: str, port: int = 443, timeout: int = 900) -> bool:
        """Wait for FDM API service to be ready with better status updates"""
        start_time = time.time()
        self._update_status(5, in_progress=True, message="Waiting for FDM service to start...")
        last_update = 0
        check_interval = 10

        while time.time() < start_time + timeout:
            try:
                response = requests.get(f"https://{ip}:{port}/api/versions", verify=False, timeout=5)
                if response.status_code in [200, 401, 403]:
                    elapsed = int(time.time() - start_time)
                    self._update_status(5, in_progress=True, message=f"FDM service ready (after {elapsed}s)")
                    print(f"FDM service ready after {elapsed} seconds")
                    return True
            except requests.exceptions.RequestException:
                pass

            elapsed = int(time.time() - start_time)
            if elapsed - last_update >= 30:
                self._update_status(5, in_progress=True, message=f"Waiting for FDM... {elapsed}/{timeout}s")
                last_update = elapsed
                print(f"Still waiting for FDM service... ({elapsed}/{timeout}s)")
            time.sleep(check_interval)

        self._update_status(5, completed=False, message="FDM service timeout")
        print(f"FDM service did not start within {timeout} seconds")
        return False

    async def configure_ftd_via_api(self, default_gateway: str = "192.168.200.254") -> bool:
        """
        Configure FTD device via Swagger API using correct HAIPv4Address structure.
        Configures interfaces GigabitEthernet0/2 and GigabitEthernet0/3 and sets default gateway.
        """
        try:
            self._update_status(5, in_progress=True, message="Adding FTD IPs and gateway...")

            # Find FTD device
            ftd_device = None
            device_name = ""
            for dev_name, dev in self.test_bed_data.devices.items():
                if getattr(dev, "type", "") == "ftd":
                    ftd_device = dev
                    device_name = dev_name
                    break

            if not ftd_device:
                self._update_status(5, completed=False, message="FTD device not found")
                return False

            # Get management IP
            mgmt_ip = None
            for intf in ftd_device.interfaces.values():
                if getattr(intf, "alias", "") == "initial":
                    mgmt_ip = intf.ipv4.ip.compressed
                    break

            if not mgmt_ip:
                self._update_status(5, completed=False, message="FTD mgmt IP not found")
                return False

            self._update_status(5, in_progress=True, message=f"Connecting to FTD at {mgmt_ip}...")
            print(f"Configuring FTD ({device_name}) at mgmt {mgmt_ip} with gateway {default_gateway}")

            # Wait for FDM
            if not self.wait_for_fdm(mgmt_ip, timeout=60):
                return False

            # Connect via Swagger connector
            connector = SwaggerConnector(ftd_device)
            if not connector.connect():
                self._update_status(5, completed=False, message="API connection failed")
                return False

            client = connector.get_swagger_client()

            # Configure FTD Interfaces
            configured_count = 0
            try:
                print("Getting existing interfaces...")
                existing_interfaces = client.Interface.getPhysicalInterfaceList().result()
                for interface in existing_interfaces.items:
                    if interface.hardwareName in ["GigabitEthernet0/2", "GigabitEthernet0/3"]:
                        target_intf = ftd_device.interfaces[interface.hardwareName]
                        body = {
                            "id": interface.id,
                            "version": interface.version,
                            "name": getattr(interface, "name", interface.hardwareName),
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
                                    "netmask": target_intf.ipv4.netmask.exploded,
                                },
                            },
                            "securityLevel": 50,
                            "description": f"Configured for {target_intf.ipv4.ip.compressed}/{target_intf.ipv4.netmask.exploded}",
                        }
                        try:
                            client.Interface.editPhysicalInterface(objId=interface.id, body=body).result()
                            configured_count += 1
                            print(
                                f"✓ Configured {interface.hardwareName}: {target_intf.ipv4.ip.compressed}/{target_intf.ipv4.netmask.exploded}"
                            )
                        except Exception as e:
                            print(f"✗ Failed to configure {interface.hardwareName}: {e}")
            except Exception as e:
                print(f"✗ Interface configuration failed: {e}")
                import traceback
                traceback.print_exc()

            # Configure default gateway
            gateway_configured = False
            try:
                print("Configuring default gateway...")
                networks_response = client.Network.getNetworkList().result()
                gateway_network = next((n for n in networks_response.items if n.name == "default_gateway"), None)

                if not gateway_network:
                    # Create network object for gateway
                    network_model = client.get_model("Network")
                    gateway_network = network_model(
                        name="default_gateway", value=default_gateway + "/32", type="network"
                    )
                    gateway_network = client.Network.addNetwork(body=gateway_network).result()
                    print(f"✓ Created network object for gateway: {default_gateway}")

                # Add static route
                route_body = {
                    "type": "staticroute",
                    "gateway": {"id": gateway_network.id, "type": "network"},
                    "metricValue": 1,
                    "selectedNetworks": [{"type": "network", "id": "any-ipv4", "name": "any-ipv4"}],
                }
                client.Routing.addStaticRouteEntry(body=route_body).result()
                print(f"✓ Default gateway configured: 0.0.0.0/0 via {default_gateway}")
                gateway_configured = True

            except Exception as e:
                print(f"✗ Gateway configuration failed: {e}")
                try:
                    simple_route_body = {
                        "type": "staticroute",
                        "gateway": default_gateway,
                        "metricValue": 1,
                        "selectedNetworks": ["any-ipv4"],
                    }
                    client.Routing.addStaticRouteEntry(body=simple_route_body).result()
                    gateway_configured = True
                    print(f"✓ Default gateway configured (simple method): {default_gateway}")
                except Exception as simple_e:
                    print(f"✗ Simple gateway method failed: {simple_e}")

            # Deploy configuration
            deployment_success = False
            try:
                print("Deploying configuration...")
                deployment_body = {
                    "type": "deploymentrequest",
                    "forceDeploy": True,
                    "ignoreWarning": True,
                }
                deployment_response = client.Deployment.addDeployment(body=deployment_body).result()
                if deployment_response:
                    deployment_success = True
                    print("✓ Configuration deployment initiated")
                    await asyncio.sleep(15)
                    print("✓ Deployment should be complete")
            except Exception as e:
                print(f"⚠ Deployment failed: {e} - manual deployment required")

            # Final status
            success = configured_count >= 1
            status_msg = f"FTD: {configured_count}/2 interfaces, gateway: {gateway_configured}"
            self._update_status(5, completed=success, message=status_msg)
            print(f"🎉 {status_msg}")

            if success:
                with self.lock:
                    self.configured_passed.add(device_name)
            else:
                with self.lock:
                    self.configured_failed.add(device_name)
            return success

        except Exception as e:
            self._update_status(5, completed=False, message=f"FTD API configuration failed: {e}")
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            if "ftd_device" in locals() and ftd_device:
                with self.lock:
                    self.configured_failed.add(device_name)
            return False

    async def full_orchestration(self) -> Dict[str, bool]:
        """Run complete orchestration with proper error handling"""
        results = {}
        try:
            results["load_testbed"] = self.load_testbed()
            if not results["load_testbed"]:
                print("❌ Testbed loading failed - stopping orchestration")
                return results

            results["server_setup"] = self.server_interfaces()
            if not results["server_setup"]:
                print("⚠️ Server setup failed - continuing anyway")

            results["router_config"] = await self.configure_routers()
            if not results["router_config"]:
                print("⚠️ Router configuration had failures - continuing anyway")

            results["ftd_initial"] = await self.configure_ftd_initial_setup()
            if not results["ftd_initial"]:
                print("⚠️ FTD initial setup incomplete - trying API configuration anyway")

            results["ftd_api"] = await self.configure_ftd_via_api()

            print("\n" + "=" * 60)
            print("ORCHESTRATION SUMMARY")
            print("=" * 60)
            for step, success in results.items():
                status = "✓ PASS" if success else "✗ FAIL"
                print(f"{step:20s}: {status}")
            print("=" * 60)
            return results

        except Exception as e:
            print(f"\n[CRITICAL ERROR] Orchestration failed: {e}")
            import traceback
            traceback.print_exc()
            return results
