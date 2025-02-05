import json
import os
from datetime import datetime

# Define paths
intent_file_path = "intent.json"
output_dir = "./configs"
os.makedirs(output_dir, exist_ok=True)

# Read the intent file
def read_intent_file(file_path):
    with open(file_path, "r") as file:
        return json.load(file)
    
def convert_router_name(router_name):
    router_number = router_name[1:]  # Extract number (e.g., R1 → 1)
    return f"i{router_number}"

# Convert IPv6 loopback address to proper router ID format (1.1.1.1)
def convert_to_router_id(router_name):
    router_number = router_name[1:]  # Extract the router number (e.g., R1 → 1)
    return f"{router_number}.{router_number}.{router_number}.{router_number}"

# Convert IPv6 loopback neighbors to proper BGP format (1::2 → 1::2)
def convert_to_neighbor_format(ipv6_addr):
    return ipv6_addr.split("/")[0]

# Check if an interface connects AS1 to AS2 (border link)
def is_border_link(router_name, interface_name, intent):
    if router_name in intent["as_numbers"]["1"]["border_routers"] and interface_name == "GigabitEthernet1/0":
        return True
    if router_name in intent["as_numbers"]["2"]["border_routers"] and interface_name == "GigabitEthernet1/0":
        return True
    return False

def generate_router_config(router_name, intent):
    config_lines = []
    now = datetime.now().strftime("%H:%M:%S UTC %a %b %d %Y")
    
    # Common Header
    config_lines.extend([
        "!",
        f"! Last configuration change at {now}",
        "!",
        "version 15.2",
        "service timestamps debug datetime msec",
        "service timestamps log datetime msec",
        "!",
        f"hostname {router_name}",
        "!",
        "boot-start-marker",
        "boot-end-marker",
        "!",
        "no aaa new-model",
        "no ip icmp rate-limit unreachable",
        "ip cef",
        "!",
        "no ip domain lookup",
        "ipv6 unicast-routing",
        "ipv6 cef",
        "!",
        "multilink bundle-name authenticated",
        "ip tcp synwait-time 5",
        "!"
    ])

    # Get Router Details
    router_data = intent["routers"][router_name]
    loopback = router_data["loopback"]
    router_number = router_name[1:]  # Extract the router number (e.g., R1 → 1)
    router_id = convert_to_router_id(router_name)

    # Get AS Info
    as_number = next(asn for asn, data in intent["as_numbers"].items() if router_name in data["routers"])
    protocol = intent["as_numbers"][as_number]["protocol"]

    # 
    	
    
    # **For AS 2, eac
    ospf_process_id = "1" if as_number == "2" else router_number

    # Interfaces
    config_lines.append(f"interface Loopback0")
    config_lines.append(" no ip address")
    config_lines.append(f" ipv6 address {loopback}")
    if protocol == "RIP":
        config_lines.append(f" ipv6 rip {router_number} enable")
    elif protocol == "OSPF":
        config_lines.append(f" ipv6 ospf {ospf_process_id} area 0")  # Correct OSPF process ID for AS 2
    config_lines.append("!")

    # Required interfaces to always include
    required_interfaces = ["FastEthernet0/0", "GigabitEthernet1/0", "GigabitEthernet2/0", "GigabitEthernet3/0"]
    for intf in required_interfaces:
        config_lines.append(f"interface {intf}")
        config_lines.append(" no ip address")

        if intf in router_data["interfaces"]:
            ipv6_addr = router_data["interfaces"][intf]
            config_lines.append(f" ipv6 address {ipv6_addr}")
            config_lines.append(" ipv6 enable")

        # Configure FastEthernet0/0 with duplex full if it doesn't exist in the description
        if intf == "FastEthernet0/0" and intf not in router_data["interfaces"]:
            config_lines.append(" duplex full")
        else:
            config_lines.append(" negotiation auto")
        if not is_border_link(router_name, intf, intent):
            if protocol == "RIP" and intf in router_data["interfaces"]:
                config_lines.append(f" ipv6 rip {router_number} enable")
            # **Fix: Do NOT enable RIP or OSPF on the AS border link (R3 ↔ R4)**
            
            if protocol == "OSPF" and intf in router_data["interfaces"]:
                config_lines.append(f" ipv6 ospf {ospf_process_id} area 0")  # Correct OSPF process ID
                


        # Do NOT shutdown if the interface has an IPv6 address
        if intf not in router_data["interfaces"]:
            config_lines.append(" shutdown")

        config_lines.append("!")

    # BGP Configuration
    config_lines.append(f"router bgp {as_number}")
    config_lines.append(f" bgp router-id {router_id}")
    config_lines.append(" bgp log-neighbor-changes")
    config_lines.append(" no bgp default ipv4-unicast")

    # Infer Full-Mesh iBGP
    as_routers = intent["as_numbers"][as_number]["routers"]
    for neighbor in as_routers:
        if neighbor != router_name:
            neighbor_loopback = convert_to_neighbor_format(intent["routers"][neighbor]["loopback"])
            config_lines.append(f" neighbor {neighbor_loopback} remote-as {as_number}")
            config_lines.append(f" neighbor {neighbor_loopback} update-source Loopback0")

    # Add eBGP neighbors from intent file
    border_routers = intent["as_numbers"][as_number].get("border_routers", {})
    if router_name in border_routers:
        neighbor_as = "2" if as_number == "1" else "1"
        neighbor_router = next(iter(intent["as_numbers"][neighbor_as]["border_routers"]))
        neighbor_ip = intent["routers"][neighbor_router]["interfaces"]["GigabitEthernet1/0"].split("/")[0]
        config_lines.append(f" neighbor {neighbor_ip} remote-as {neighbor_as}")

    # BGP Address Family
    config_lines.append(" !")
    config_lines.append(" address-family ipv4")
    config_lines.append(" exit-address-family")
    config_lines.append(" !")
    config_lines.append(" address-family ipv6")

    # **✅ Advertise Loopback Addresses in BGP**
    config_lines.append(f"  network {loopback.split('/')[0]}/128")  # Add the loopback to BGP

    for intf in router_data["interfaces"].values():
        network = intf.rsplit("::", 1)[0] + "::/64"
        config_lines.append(f"  network {network}")
    for neighbor in as_routers:
        if neighbor != router_name:
            neighbor_loopback = convert_to_neighbor_format(intent["routers"][neighbor]["loopback"])
            config_lines.append(f"  neighbor {neighbor_loopback} activate")
    # Add eBGP neighbor activation
    if router_name in border_routers:
        neighbor_ip = intent["routers"][neighbor_router]["interfaces"]["GigabitEthernet1/0"].split("/")[0]
        config_lines.append(f"  neighbor {neighbor_ip} activate")
    config_lines.append(" exit-address-family")
    config_lines.append("!")

    
    

    # Final Footer
    config_lines.extend([
        "ip forward-protocol nd",
        "no ip http server",
        "no ip http secure-server",
    ])

    # Routing Configuration
    if protocol == "RIP":
        config_lines.append(f"ipv6 router rip {router_number}")
        config_lines.append(" redistribute connected")
        config_lines.append("!")
    if protocol == "OSPF":
        config_lines.append(f"ipv6 router ospf {ospf_process_id}")  # Correct process ID
        config_lines.append(f" router-id {router_id}")
        config_lines.append("!")
        
    config_lines.extend([
        "!",
        "control-plane",
        "!",
        "line con 0",
        " exec-timeout 0 0",
        " privilege level 15",
        " logging synchronous",
        " stopbits 1",
        "line aux 0",
        " exec-timeout 0 0",
        " privilege level 15",
        " logging synchronous",
        " stopbits 1",
        "line vty 0 4",
        " login",
        "!",
        "end"
    ])

    return "\n".join(config_lines)

# Write configuration files


def write_config_files(intent):
    for router in intent["routers"]:
        config = generate_router_config(router, intent)
        new_filename = convert_router_name(router) + "_startup-config.cfg"
        with open(f"./configs/{new_filename}", "w") as file:
            file.write(config)

# Main execution
intent = read_intent_file(intent_file_path)
write_config_files(intent)

print("✅ Configuration files generated successfully!")
