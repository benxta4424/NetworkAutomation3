results = {}

while True:
    add_switch = input("Add switch (or press 'q' to quit): ")

    if add_switch == 'q':
        break

    if add_switch in results:
        print("Switch already exists!")
        continue

    results[add_switch] = {}

    while True:
        add_port = input(f"Add port to switch '{add_switch}' (or 'q' to finish adding ports): ")
        if add_port == 'q':
            break

        if add_port in results[add_switch]:
            print("Port already exists!")
            continue
        results[add_switch][add_port] = {"vlans": set()}

        while True:
            add_vlans = input("Add VLANs one by one or press 'q' when done: ")
            if add_vlans == 'q':
                break
            if add_vlans.isdigit():
                vlan_num = int(add_vlans)
                results[add_switch][add_port]["vlans"].add(vlan_num)
            else:
                print("Please enter a valid integer VLAN number.")

print(results)
