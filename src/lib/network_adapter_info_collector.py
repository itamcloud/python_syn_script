import psutil
import socket
import platform
import subprocess
import re

import os
import sys
import mysql.connector


DB_HOST="68.178.156.243"
DB_USER="itamcloud"
DB_PASSWORD="Kgl0b@ltech"
DB_NAME="ITAMCloud"


class NetworkAdapterInfoCollector:
    def __init__(self, company_id, asset_id):
        self.asset_id = asset_id
        self.company_id = company_id

    def get_default_gateway(self):
        system = platform.system()
        try:
            if system == "Windows":
                output = subprocess.check_output("route print 0.0.0.0", shell=True, text=True)
                for line in output.splitlines():
                    if line.strip().startswith("0.0.0.0"):
                        parts = line.split()
                        if len(parts) >= 4:
                            return parts[2]
            elif system == "Darwin":
                output = subprocess.check_output("route -n get default", shell=True, text=True)
                match = re.search(r'gateway: ([\d.]+)', output)
                if match:
                    return match.group(1)
            elif system == "Linux":
                output = subprocess.check_output("ip route show default", shell=True, text=True)
                match = re.search(r'default via ([\d.]+)', output)
                if match:
                    return match.group(1)
        except Exception:
            pass
        return None

    def get_dhcp_status(self, interface):
        system = platform.system()
        try:
            if system == "Windows":
                output = subprocess.check_output(
                    f'netsh interface ip show config name="{interface}"',
                    shell=True, text=True, errors='ignore'
                )
                if "DHCP enabled: Yes" in output or "DHCP is enabled" in output:
                    return "Yes"
            elif system == "Darwin":
                try:
                    output = subprocess.check_output(
                        ["ipconfig", "getpacket", interface],
                        text=True
                    )
                    if "dhcp_message_type" in output:
                        return "Yes"
                except subprocess.CalledProcessError:
                    return "No"
            elif system == "Linux":
                # Try to determine if DHCP is enabled using nmcli (NetworkManager)
                try:
                    nmcli_output = subprocess.check_output(
                        f"nmcli device show {interface}", shell=True, text=True
                    )
                    if "IP4.DHCP" in nmcli_output:
                        return "Yes"
                except Exception:
                    pass
                # Fallback: check dhclient lease files (not always reliable)
                try:
                    leases = subprocess.check_output(
                        f"ls /var/lib/dhcp/dhclient.*{interface}*.leases", shell=True, text=True
                    )
                    if leases.strip():
                        return "Yes"
                except Exception:
                    pass
        except Exception:
            pass
        return "No"

    def collect_network_info(self):
        network_info = []
        system = platform.system()

        # Determine which family represents a MAC address for this platform
        if hasattr(socket, "AF_LINK"):
            MAC_FAMILY = socket.AF_LINK
        elif hasattr(psutil, "AF_LINK"):
            MAC_FAMILY = psutil.AF_LINK
        elif hasattr(socket, "AF_PACKET"):
            MAC_FAMILY = socket.AF_PACKET
        else:
            MAC_FAMILY = None  # fallback

        for interface, addrs in psutil.net_if_addrs().items():
            ip_address = None
            subnet_mask = None
            mac_address = None
            for addr in addrs:
                # IPv4 address
                if addr.family == socket.AF_INET:
                    if not ip_address:  # Take the first IPv4 only
                        ip_address = addr.address
                        subnet_mask = addr.netmask
                # MAC address (cross-platform handling)
                if MAC_FAMILY and addr.family == MAC_FAMILY:
                    if addr.address and addr.address != '00:00:00:00:00:00':
                        mac_address = addr.address

            stats = psutil.net_if_stats().get(interface)
            status = 'Up' if stats and stats.isup else 'Down'
            speed = stats.speed if stats and hasattr(stats, 'speed') else 0
            default_gateway = self.get_default_gateway()
            dhcp_enabled = self.get_dhcp_status(interface)

            network_info.append({
                'adapter_name': interface,
                'manufacturer': '',  # Not available via psutil
                'mac_address': mac_address,
                'interface_type': '',  # Optional
                'ip_address': ip_address,
                'subnet_mask': subnet_mask,
                'default_gateway': default_gateway,
                'dhcp_enabled': 1 if dhcp_enabled == 'Yes' else 0,
                'speed': speed,
                'status': status
            })
        return network_info

    def insert_network_info(self, network_info):
        """
        Insert system_info into MySQL database.
        Args:
            system_info (dict): Collected hardware info.
            asset_id (int): Asset identifier.
            company_id (int): Company identifier.
        """
        connection = None
        cursor = None
        try:
            connection = mysql.connector.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME
            )
            cursor = connection.cursor()
            query = """
                INSERT INTO assets_network_adapter_info 
                (asset_id, adapter_name, manufacturer, mac_address, interface_type, ip_address, subnet_mask, default_gateway, dhcp_enabled, speed, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            for adapter in network_info:
                values = (
                    self.asset_id,
                    adapter['adapter_name'],
                    adapter['manufacturer'],
                    adapter['mac_address'],
                    adapter['interface_type'],
                    adapter['ip_address'],
                    adapter['subnet_mask'],
                    adapter['default_gateway'],
                    adapter['dhcp_enabled'],
                    adapter['speed'],
                    adapter['status']
                )
            cursor.execute(query, values)
            connection.commit()
            print("✅ System info inserted successfully.")
            print("Network adapter information inserted successfully.")
        except mysql.connector.Error as err:
            print(f"❌ MySQL error: {err}")
        except Exception as e:
            print(f"❌ General error: {e}")
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    def get_network_info(self):
        print("Collecting network adapter information...")
        # Collect network information
        network_info = self.collect_network_info()
        if not network_info:
            print("❌ No network adapter information found.")
            return
        print(f"System Network Information: {network_info}")
        self.insert_network_info(network_info)
