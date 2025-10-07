
from pyats import aetest, topology
from genie.libs.conf.interface.iosxe import Interface
from genie.libs.conf.static_routing import StaticRouting
from pyats.topology import Device


class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def load_testbed(self, steps):
        with steps.start("Load testbed"):
            tb = topology.loader.load('genie_testbed.yaml')
            self.parent.parameters.update(tb=tb)


class ConfigureGenie(aetest.Testcase):
    @aetest.setup
    def connect(self, steps):
        tb = self.parent.parameters.get("tb")
        self.dev: Device = tb.devices.CSR
        self.dev.connect(log_stdout=True)

    @aetest.test
    def configure_interfaces(self, steps):
        with steps.start("Configure interface 1"):
            intf = Interface(
                name='GigabitEthernet2'
            )
            intf.device = self.dev
            intf.ipv4 = self.dev.interfaces['GigabitEthernet2'].ipv4
            config = intf.build_config(apply=False)
            self.dev.configure(config.cli_config.data)
            print(config)

        with steps.start("Configure interface 2"):
            intf = Interface(
                name='GigabitEthernet3'
            )
            intf.device = self.dev
            intf.ipv4 = self.dev.interfaces['GigabitEthernet3'].ipv4
            config = intf.build_config(apply=False)
            self.dev.configure(config.cli_config.data)
            print(config)

        with steps.start("Configure static routing"):
            route = StaticRouting()
            route.devices = [self.dev]
            route.device_attr[self.dev].vrf_attr["default"].address_family_attr["ipv4"].route_attr["192.168.205.0/24"].next_hop_attr["192.168.204.4"]
            config = route.build_config(apply=False)
            self.dev.configure(config[self.dev.name].cli_config.data)

if __name__ == '__main__':
    aetest.main()