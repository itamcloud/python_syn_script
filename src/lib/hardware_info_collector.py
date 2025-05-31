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
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database config (store securely in production!)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "")


class HardwareInfoCollector:

    def __init__(self, company_id, asset_id):
        self.asset_id = asset_id
        self.company_id = company_id
    """
    Collects hardware information for different operating systems.
    """
    def get_linux_system_info(self):
        """
        Collect hardware info on Linux using /proc and sysfs.
        Returns:
            dict: System information.
        """
        system_info = {}

        # CPU Info
        cpu_model = "Unknown"
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        cpu_model = line.strip().split(":")[1].strip()
                        break
        except Exception as e:
            print(f"[WARN] Could not read CPU info: {e}")
        system_info['cpu_id'] = cpu_model
        system_info['cpu_type'] = platform.machine()

        # Memory Info
        try:
            system_info['memory_total'] = psutil.virtual_memory().total
        except Exception as e:
            print(f"[WARN] Could not read memory info: {e}")
            system_info['memory_total'] = None

        # Battery Info
        try:
            battery = psutil.sensors_battery()
            if battery:
                # Linux battery info is limited via psutil
                system_info.update({
                    'battery_vendor': "Unknown",
                    'battery_model': "Unknown",
                    'battery_serial_number': "Unknown",
                    'battery_voltage': None,
                    'battery_cycle_count': None
                })
            else:
                system_info.update({
                    'battery_vendor': None,
                    'battery_model': None,
                    'battery_serial_number': None,
                    'battery_voltage': None,
                    'battery_cycle_count': None
                })
        except Exception as e:
            print(f"[WARN] Battery info error: {e}")
            system_info.update({k: None for k in [
                'battery_vendor', 'battery_model', 'battery_serial_number', 'battery_voltage', 'battery_cycle_count'
            ]})

        # BIOS version
        bios_version = "Unknown"
        try:
            bios_path = "/sys/class/dmi/id/bios_version"
            if os.path.exists(bios_path):
                with open(bios_path, "r") as f:
                    bios_version = f.read().strip()
        except Exception as e:
            print(f"[WARN] BIOS info error: {e}")
        system_info['bios'] = bios_version

        # TPM Info
        tpm_path = "/sys/class/tpm/tpm0/"
        system_info['tpm_manufacturer'] = "Unknown"
        system_info['tpm_version'] = "Unknown"
        system_info['tpm_activation_status'] = "Unknown"
        system_info['tpm_ownership_status'] = "Unknown"
        if os.path.exists(tpm_path):
            try:
                with open(os.path.join(tpm_path, "manufacturer_name"), "r") as f:
                    system_info['tpm_manufacturer'] = f.read().strip()
            except Exception as e:
                print(f"[WARN] TPM manufacturer read error: {e}")
            try:
                with open(os.path.join(tpm_path, "tpm_version_major"), "r") as f:
                    major = f.read().strip()
                with open(os.path.join(tpm_path, "tpm_version_minor"), "r") as f:
                    minor = f.read().strip()
                system_info['tpm_version'] = f"{major}.{minor}"
            except Exception as e:
                print(f"[WARN] TPM version read error: {e}")

        return system_info

    def get_windows_system_info(self):
        """
        Collect hardware info on Windows using WMI & psutil.
        Returns:
            dict: System information.
        """
        system_info = {}

        # CPU Info
        system_info['cpu_id'] = platform.processor()
        system_info['cpu_type'] = platform.machine()

        # Memory Info
        try:
            system_info['memory_total'] = psutil.virtual_memory().total
        except Exception as e:
            print(f"[WARN] Could not read memory info: {e}")
            system_info['memory_total'] = None

        # Battery Info
        try:
            import wmi
            c = wmi.WMI()
            batteries = c.Win32_Battery()
            if batteries:
                battery = batteries[0]
                system_info['battery_vendor'] = getattr(battery, 'Manufacturer', 'Unknown')
                system_info['battery_model'] = getattr(battery, 'Name', 'Unknown')
                system_info['battery_serial_number'] = getattr(battery, 'SerialNumber', 'Unknown')
                system_info['battery_voltage'] = getattr(battery, 'DesignVoltage', None)
                system_info['battery_cycle_count'] = getattr(battery, 'CycleCount', None)
            else:
                # Fallback to psutil
                battery = psutil.sensors_battery()
                if battery:
                    system_info.update({
                        'battery_vendor': "Unknown",
                        'battery_model': "Unknown",
                        'battery_serial_number': "Unknown",
                        'battery_voltage': None,
                        'battery_cycle_count': None
                    })
                else:
                    system_info.update({k: None for k in [
                        'battery_vendor', 'battery_model', 'battery_serial_number', 'battery_voltage', 'battery_cycle_count'
                    ]})
        except Exception as e:
            print(f"[WARN] Battery info error: {e}")
            battery = psutil.sensors_battery()
            if battery:
                system_info.update({
                    'battery_vendor': "Unknown",
                    'battery_model': "Unknown",
                    'battery_serial_number': "Unknown",
                    'battery_voltage': None,
                    'battery_cycle_count': None
                })
            else:
                system_info.update({k: None for k in [
                    'battery_vendor', 'battery_model', 'battery_serial_number', 'battery_voltage', 'battery_cycle_count'
                ]})

        # BIOS version
        bios_version = "Unknown"
        try:
            import wmi
            c = wmi.WMI()
            for bios in c.Win32_BIOS():
                bios_version = getattr(bios, 'SMBIOSBIOSVersion', 'Unknown')
                break
        except Exception as e:
            print(f"[WARN] BIOS info error: {e}")
        system_info['bios'] = bios_version

        # TPM info (via PowerShell)
        system_info['tpm_manufacturer'] = "Unknown"
        system_info['tpm_version'] = "Unknown"
        system_info['tpm_activation_status'] = "Unknown"
        system_info['tpm_ownership_status'] = "Unknown"
        try:
            ps_cmd = [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-WmiObject -Namespace 'Root\\CIMv2\\Security\\MicrosoftTpm' -Class Win32_Tpm | "
                "Select-Object -Property ManufacturerID, ManufacturerVersion, IsActivated_InitialValue, IsOwned_InitialValue | ConvertTo-Json"
            ]
            result = subprocess.run(ps_cmd, capture_output=True, text=True, timeout=10)
            if result.stdout:
                tpm_info = json.loads(result.stdout)
                tpm = tpm_info[0] if isinstance(tpm_info, list) and tpm_info else tpm_info
                system_info['tpm_manufacturer'] = tpm.get('ManufacturerID', 'Unknown')
                system_info['tpm_version'] = tpm.get('ManufacturerVersion', 'Unknown')
                system_info['tpm_activation_status'] = tpm.get('IsActivated_InitialValue', 'Unknown')
                system_info['tpm_ownership_status'] = tpm.get('IsOwned_InitialValue', 'Unknown')
        except Exception as e:
            print(f"[WARN] TPM info error: {e}")

        return system_info

    def get_macos_system_info(self):
        """
        Collect hardware info on macOS using sysctl, ioreg, and system_profiler.
        Returns:
            dict: System information.
        """
        system_info = {}

        # CPU Info
        try:
            cpu_info = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"]
            ).decode().strip()
        except Exception as e:
            print(f"[WARN] Could not read CPU info: {e}")
            cpu_info = platform.processor()
        system_info['cpu_id'] = cpu_info
        system_info['cpu_type'] = platform.machine()

        # Memory Info
        try:
            memory_bytes = int(
                subprocess.check_output(["sysctl", "-n", "hw.memsize"]).decode().strip()
            )
        except Exception as e:
            print(f"[WARN] Memory info error: {e}")
            memory_bytes = psutil.virtual_memory().total
        system_info['memory_total'] = memory_bytes

        # Battery Info
        try:
            ioreg = subprocess.check_output([
                "ioreg", "-rc", "AppleSmartBattery"
            ]).decode()
            def extract_ioreg_value(field):
                for line in ioreg.splitlines():
                    if field in line:
                        return line.split("=")[-1].strip().replace("\"", "")
                return None

            system_info['battery_vendor'] = extract_ioreg_value('Manufacturer') or "Unknown"
            system_info['battery_model'] = extract_ioreg_value('DeviceName') or "Unknown"
            system_info['battery_serial_number'] = extract_ioreg_value('BatterySerialNumber') or "Unknown"
            voltage = extract_ioreg_value('Voltage')
            system_info['battery_voltage'] = int(voltage) if voltage and voltage.isdigit() else None
            cycle_count = extract_ioreg_value('CycleCount')
            system_info['battery_cycle_count'] = int(cycle_count) if cycle_count and cycle_count.isdigit() else None
        except Exception as e:
            print(f"[WARN] Battery info error: {e}")
            system_info.update({k: None for k in [
                'battery_vendor', 'battery_model', 'battery_serial_number', 'battery_voltage', 'battery_cycle_count'
            ]})

        # BIOS version (Boot ROM/SMC version for Mac)
        try:
            bios_version = subprocess.check_output(
                ["system_profiler", "SPHardwareDataType"]
            ).decode()
            for line in bios_version.splitlines():
                if "Boot ROM Version" in line or "SMC Version (system)" in line:
                    system_info['bios'] = line.split(":")[-1].strip()
                    break
            else:
                system_info['bios'] = "Unknown"
        except Exception as e:
            print(f"[WARN] BIOS info error: {e}")
            system_info['bios'] = "Unknown"

        # TPM Info (Apple T2 chip as TPM analog)
        try:
            t2_info = subprocess.check_output(
                ["system_profiler", "SPiBridgeDataType"]
            ).decode()
            if "Apple T2 Security Chip" in t2_info:
                system_info['tpm_manufacturer'] = "Apple"
                for line in t2_info.splitlines():
                    if "Model Identifier" in line:
                        system_info['tpm_version'] = line.split(":")[-1].strip()
                        break
                else:
                    system_info['tpm_version'] = "T2"
                system_info['tpm_activation_status'] = "Present"
                system_info['tpm_ownership_status'] = "Managed by macOS"
            else:
                system_info.update({
                    'tpm_manufacturer': "None",
                    'tpm_version': "None",
                    'tpm_activation_status': "None",
                    'tpm_ownership_status': "None"
                })
        except Exception as e:
            print(f"[WARN] TPM/T2 info error: {e}")
            system_info.update({
                'tpm_manufacturer': "Unknown",
                'tpm_version': "Unknown",
                'tpm_activation_status': "Unknown",
                'tpm_ownership_status': "Unknown"
            })

        return system_info

    def get_unique_asset_id(self):
        """
            Returns a unique hardware identifier for the current machine using the best available method for each OS.
            On Windows: Returns UUID (or BIOS serial as fallback).
            On Linux: Returns product_uuid from DMI (or machine-id as fallback).
            On macOS: Returns hardware serial number.
            Returns None if not available.
            """
        system = platform.system().lower()
        unique_id = None
        try:
            if system == "windows":
                try:
                    import wmi
                    c = wmi.WMI()
                    for sys in c.Win32_ComputerSystemProduct():
                        if sys.UUID and sys.UUID != "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF":
                            unique_id = sys.UUID
                            break
                    if not unique_id:
                        for bios in c.Win32_BIOS():
                            if bios.SerialNumber and "O.E.M." not in bios.SerialNumber:
                                unique_id = bios.SerialNumber
                                break
                except Exception:
                    pass

            elif system == "linux":
                try:
                    # Try product_uuid
                    with open("/sys/class/dmi/id/product_uuid", "r") as f:
                        uuid = f.read().strip()
                        if uuid and uuid != "None":
                            unique_id = uuid
                except Exception:
                    pass
                if not unique_id:
                    # Try /etc/machine-id as fallback
                    try:
                        with open("/etc/machine-id", "r") as f:
                            mid = f.read().strip()
                            if mid:
                                unique_id = mid
                    except Exception:
                        pass

            elif system == "darwin":  # macOS
                try:
                    result = subprocess.check_output(
                        "system_profiler SPHardwareDataType | awk '/Serial/ {print $4}'",
                        shell=True
                    ).decode().strip()
                    if result and result != "Unknown":
                        unique_id = result
                except Exception:
                    pass

        except Exception as e:
            print(f"[WARN] Could not determine unique asset id: {e}")

        return unique_id
    
    def insert_hardware_info(self ,system_info):
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
            INSERT INTO assets_hardware_info (
                asset_id, company_id, serial_number, make, model, version, motherboard_serial_no,
                cpu_id, cpu_type, bios, tpm_manufacturer, tpm_version, tpm_activation_status,
                tpm_ownership_status, battery_vendor, battery_model, battery_serial_number,
                battery_voltage, battery_cycle_count, memory_slots_used, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE
                company_id = VALUES(company_id),
                serial_number = VALUES(serial_number),
                make = VALUES(make),
                model = VALUES(model),
                version = VALUES(version),
                motherboard_serial_no = VALUES(motherboard_serial_no),
                cpu_id = VALUES(cpu_id),
                cpu_type = VALUES(cpu_type),
                bios = VALUES(bios),
                tpm_manufacturer = VALUES(tpm_manufacturer),
                tpm_version = VALUES(tpm_version),
                tpm_activation_status = VALUES(tpm_activation_status),
                tpm_ownership_status = VALUES(tpm_ownership_status),
                battery_vendor = VALUES(battery_vendor),
                battery_model = VALUES(battery_model),
                battery_serial_number = VALUES(battery_serial_number),
                battery_voltage = VALUES(battery_voltage),
                battery_cycle_count = VALUES(battery_cycle_count),
                memory_slots_used = VALUES(memory_slots_used),
                created_at = NOW()
            """

            data = (
                self.asset_id,
                self.company_id,
                "Unknown",                  # serial_number
                "Unknown",                  # make
                "Unknown",                  # model
                "Unknown",                  # version
                "Unknown",                  # motherboard_serial_no
                system_info.get('cpu_id'),
                system_info.get('cpu_type'),
                system_info.get('bios'),
                system_info.get('tpm_manufacturer'),
                system_info.get('tpm_version'),
                system_info.get('tpm_activation_status'),
                system_info.get('tpm_ownership_status'),
                system_info.get('battery_vendor'),
                system_info.get('battery_model'),
                system_info.get('battery_serial_number'),
                system_info.get('battery_voltage'),
                system_info.get('battery_cycle_count'),
                system_info.get('memory_total')
            )

            cursor.execute(insert_query, data)
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

    def get_system_info(self):
        """
        Collect system information based on the current platform.
        Returns:
            dict: Collected system information.
        """
        platform_name = platform.system().lower()
        if platform_name == "windows":
            print("🔍 Collecting Windows system information...")
            system_info = self.get_windows_system_info()
        elif platform_name == "linux":
            print("🔍 Collecting Linux system information...")
            system_info = self.get_linux_system_info()
        elif platform_name == "darwin":  # macOS
            print("🔍 Collecting macOS system information...")
            system_info = self.get_macos_system_info() 
        else:
            print("❌ Unsupported platform:", platform_name)
            exit(1)
        # Print the collected system information
        print(f"System Headware Information Collected:{system_info}")
        self.insert_hardware_info(system_info)
