rip_commands = [
    "\n",
    "conf t",
    "router rip",
    "version 2",
    "no auto-summary",
    "network 192.168.200.0",  # Management network
    "network 192.168.10.0",   # Guest network (IOU1)
    "network 192.168.20.0",   # IOU1-Router link
    "network 192.168.30.0",   # Router-CSR link
    "network 192.168.40.0",   # CSR-FTD link
    "network 192.168.50.0",   # FTD external
    "exit",
    "exit"
]