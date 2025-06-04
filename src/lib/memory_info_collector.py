"""
hardware_info_collector.py

This module collects hardware information from Windows, Linux, or macOS systems and (optionally) inserts it into a MySQL database.
It uses platform-specific methods for accurate data retrieval and follows best practices for exception handling and code documentation.

Author: [Your Name]
Date: [YYYY-MM-DD]
"""

import psutil
import platform
import os
import mysql.connector
import subprocess
import json
import re


# Database config (store securely in production!)
DB_HOST="68.178.156.243"
DB_USER="itamcloud"
DB_PASSWORD="Kgl0b@ltech"
DB_NAME="ITAMCloud"


class MemHardwareInfoCollector:

    def __init__(self, company_id, asset_id):
        self.asset_id = asset_id
        self.company_id = company_id
    """
    Collects hardware information for different operating systems.
    """
    def get_linux_memory_info(self):
        memory_info = []
        try:
            output = subprocess.check_output("sudo dmidecode --type memory", shell=True).decode()
            slots = output.split("Memory Device")
            slot_number = 0

            for slot in slots[1:]:
                slot_number += 1
                info = {
                    "slot_number": slot_number,
                    "manufacturer": self.get_dmi_value(slot, "Manufacturer"),
                    "capacity": self.parse_capacity(self.get_dmi_value(slot, "Size")),
                    "type": self.get_dmi_value(slot, "Type"),
                    "speed": self.parse_speed(self.get_dmi_value(slot, "Speed")),
                    "configured_speed": self.parse_speed(self.get_dmi_value(slot, "Configured Clock Speed")),
                    "form_factor": self.get_dmi_value(slot, "Form Factor"),
                    "part_number": self.get_dmi_value(slot, "Part Number"),
                    "serial_number": self.get_dmi_value(slot, "Serial Number")
                }
                if info["capacity"] > 0:
                    memory_info.append(info)
        except Exception as e:
            print("Linux memory info error:", e)
        return memory_info

    def get_windows_memory_info(self):
        memory_info = []
        try:
            # Query memory chip details using WMIC
            output = subprocess.check_output(
                'wmic MEMORYCHIP get BankLabel,Capacity,Manufacturer,Speed,MemoryType,PartNumber,SerialNumber,FormFactor /format:list',
                shell=True
            ).decode(errors='ignore')
            chips = [c.strip() for c in output.split('\n\n') if c.strip()]
            slot_number = 0
            for chip in chips:
                slot_number += 1
                def get_value(key):
                    match = re.search(rf"{key}=(.*)", chip)
                    return match.group(1).strip() if match else None
                # Parse capacity to int
                raw_capacity = get_value('Capacity')
                capacity = int(raw_capacity) if raw_capacity and raw_capacity.isdigit() else 0
                # Parse speed to int
                raw_speed = get_value('Speed')
                speed = int(raw_speed) if raw_speed and raw_speed.isdigit() else None
                memory_info.append({
                    "slot_number": slot_number,
                    "manufacturer": get_value('Manufacturer'),
                    "capacity": capacity,  # In bytes
                    "type": get_value('MemoryType'),  # Numeric code for DDR type, mapping available if needed
                    "speed": speed,  # In MHz
                    "configured_speed": speed,  # Not directly available, use speed
                    "form_factor": get_value('FormFactor'),
                    "part_number": get_value('PartNumber'),
                    "serial_number": get_value('SerialNumber'),
                })
        except Exception as e:
            print("Windows memory info error:", e)
        return memory_info

    def get_mac_memory_info(self):
        memory_info = []
        try:
            output = subprocess.check_output(
                ["system_profiler", "SPMemoryDataType"],
                text=True
            )

            # Use finditer to get all BANK blocks (BANK ...:)
            # Each block starts with BANK ...: and ends before the next BANK ...: or the end of the string
            slot_pattern = re.compile(
                r'^\s*(BANK [^:]+:)([\s\S]*?)(?=^\s*BANK [^:]+:|\Z)', re.MULTILINE
            )
            slots = slot_pattern.finditer(output)
            slot_number = 0

            for match in slots:
                slot_number += 1
                slot_label = match.group(1)
                slot_info = match.group(2)
                def get_value(key):
                    match_val = re.search(rf'{re.escape(key)}:\s*(.*)', slot_info)
                    return match_val.group(1).strip() if match_val else None

                size = get_value("Size")
                if size and size != "Empty":
                    size_match = re.match(r"(\d+)\s*(GB|MB)", size)
                    capacity = 0
                    if size_match:
                        sz, unit = size_match.groups()
                        capacity = int(sz) * (1024**3 if unit == "GB" else 1024**2)
                    else:
                        capacity = 0
                    speed = get_value("Speed")
                    speed_val = None
                    if speed:
                        speed_match = re.match(r"(\d+)\s*MHz", speed)
                        speed_val = int(speed_match.group(1)) if speed_match else None
                    memory_info.append({
                        "slot_number": slot_number,
                        "bank_label": slot_label.strip(),
                        "manufacturer": get_value("Manufacturer"),
                        "capacity": capacity,
                        "type": get_value("Type"),
                        "speed": speed_val,
                        "configured_speed": speed_val,
                        "form_factor": None,
                        "part_number": get_value("Part Number"),
                        "serial_number": get_value("Serial Number"),
                    })
        except Exception as e:
            print("macOS memory info error:", e)
        return memory_info

    def get_dmi_value(self, block, key):
        match = re.search(rf"{key}:\s*(.+)", block)
        return match.group(1).strip() if match else "Unknown"

    def parse_capacity(self, value):
        if not value or "No Module" in value:
            return 0
        match = re.match(r"(\d+)\s*(MB|GB)", value)
        if match:
            size = int(match.group(1))
            unit = match.group(2)
            return size * 1024 * 1024 if unit == "MB" else size * 1024**3
        return 0

    def parse_speed(self, value):
        match = re.match(r"(\d+)", value)
        return int(match.group(1)) if match else None
  
    def insert_hardware_info(self ,records, asset_id):
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
            insert_query = """
                INSERT INTO assets_memory_info
                (asset_id, slot_number, manufacturer, capacity, type, speed, configured_speed, form_factor, part_number, serial_number)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            values = [
                (
                    asset_id,
                    item["slot_number"],
                    item["manufacturer"],
                    item["capacity"],
                    item["type"],
                    item["speed"],
                    item["configured_speed"],
                    item["form_factor"],
                    item["part_number"],
                    item["serial_number"]
                ) for item in records
            ]
            records_fixed = [
                (json.dumps(rec[0]), *rec[1:]) for rec in values
            ]
            cursor.executemany(insert_query, records_fixed)
            connection.commit()
            print("✅ System info inserted successfully.")

        except mysql.connector.Error as err:
            print(f"❌ MySQL error: {err}")
        except Exception as e:
            print(f"❌ General error: {e}")
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    def get_memnory_info(self):
        """
        Collect system information based on the current platform.
        Returns:
            dict: Collected system information.
        """
        platform_name = platform.system().lower()
        if platform_name == "windows":
            print("🔍 Collecting Windows system information...")
            system_info = self.get_windows_memory_info()
        elif platform_name == "linux":
            print("🔍 Collecting Linux system information...")
            system_info = self.get_linux_memory_info()
        elif platform_name == "darwin":  # macOS
            print("🔍 Collecting macOS system information...")
            system_info = self.get_mac_memory_info() 
        else:
            print("❌ Unsupported platform:", platform_name)
            exit(1)
        # Print the collected system information
        print(f"System Memory Information Collected:{system_info}")
        # Insert the collected system information into the database
        self.insert_hardware_info(system_info, self.asset_id)
