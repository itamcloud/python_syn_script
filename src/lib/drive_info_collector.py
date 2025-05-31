import subprocess
import re
import platform
import psutil
from dotenv import load_dotenv
import os
import mysql.connector
import json

# Load environment variables from .env file
load_dotenv()

# Database config (store securely in production!)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "")

class DriveInfoCollector:
    # Linux method (from your example, unchanged)
    def get_linux_drive_info(self, device_name):
        """
        Get model, serial, interface, and type for a Linux block device.
        """
        try:
            if device_name.startswith("loop") or device_name.startswith("ram"):
                return None  # Skip virtual devices

            result = subprocess.run(
                ['udevadm', 'info', '--query=all', f'--name=/dev/{device_name}'],
                capture_output=True, text=True, check=True
            )

            info = result.stdout
            model = re.search(r'ID_MODEL=(.*)', info)
            serial = re.search(r'ID_SERIAL_SHORT=(.*)', info)
            interface = re.search(r'ID_BUS=(.*)', info)
            drive_type = re.search(r'ID_TYPE=(.*)', info)

            return {
                "model": model.group(1) if model else "Unknown",
                "serial_number": serial.group(1) if serial else "Unknown",
                "interface_type": interface.group(1) if interface else "Unknown",
                "drive_type": drive_type.group(1) if drive_type else "Unknown"
            }
        except Exception as e:
            print(f"Error fetching udevadm info for /dev/{device_name}: {e}")
            return {
                "model": "Unknown",
                "serial_number": "Unknown",
                "interface_type": "Unknown",
                "drive_type": "Unknown"
            }

    def get_windows_drive_info(self, device_index):
        try:
            query = f"wmic diskdrive where Index={device_index} get Model,SerialNumber,InterfaceType,MediaType /format:list"
            result = subprocess.run(
                query,
                capture_output=True, text=True, shell=True, check=True
            )
            info = result.stdout
            model = re.search(r'Model=(.*)', info)
            serial = re.search(r'SerialNumber=(.*)', info)
            interface = re.search(r'InterfaceType=(.*)', info)
            drive_type = re.search(r'MediaType=(.*)', info)

            return {
                "model": model.group(1).strip() if model else "Unknown",
                "serial_number": serial.group(1).strip() if serial else "Unknown",
                "interface_type": interface.group(1).strip() if interface else "Unknown",
                "drive_type": drive_type.group(1).strip() if drive_type else "Unknown"
            }
        except Exception as e:
            print(f"Error fetching WMIC info for disk index {device_index}: {e}")
            return {
                "model": "Unknown",
                "serial_number": "Unknown",
                "interface_type": "Unknown",
                "drive_type": "Unknown"
            }

    def get_mac_drive_info(self, disk_identifier):
        """
        Get model, serial, interface, and type for a macOS disk using system_profiler and diskutil.
        disk_identifier should be like 'disk0', 'disk1', etc.
        """
        try:
            # Get disk info from system_profiler
            sp_result = subprocess.run(
                ['system_profiler', 'SPStorageDataType'],
                capture_output=True, text=True, check=True
            )
            sp_info = sp_result.stdout

            # Find the block for the disk
            disk_block = re.search(rf'(?s)(\w.*{disk_identifier}.*?(\n\n|\Z))', sp_info)
            block = disk_block.group(1) if disk_block else ""

            # Model
            model = re.search(r'Media Name: (.*)', block)
            # Serial number (can be missing, try with diskutil)
            serial = re.search(r'Serial Number: (.*)', block)
            # Interface type
            interface = re.search(r'Protocol: (.*)', block)
            # Type (SSD/HDD)
            drive_type = re.search(r'Media Type: (.*)', block)

            # Fallback: Try diskutil info for serial if not found
            if not serial:
                du_result = subprocess.run(
                    ['diskutil', 'info', disk_identifier],
                    capture_output=True, text=True, check=True
                )
                du_info = du_result.stdout
                serial = re.search(r'Disk / Partition UUID: (.*)', du_info)  # not a real serial, but a unique ID

            return {
                "model": model.group(1).strip() if model else "Unknown",
                "serial_number": serial.group(1).strip() if serial else "Unknown",
                "interface_type": interface.group(1).strip() if interface else "Unknown",
                "drive_type": drive_type.group(1).strip() if drive_type else "Unknown"
            }
        except Exception as e:
            print(f"Error fetching drive info for {disk_identifier} on macOS: {e}")
            return {
                "model": "Unknown",
                "serial_number": "Unknown",
                "interface_type": "Unknown",
                "drive_type": "Unknown"
            }
        
    @staticmethod
    def insert_driver_info(records):
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
                INSERT INTO assets_drives_info
                (asset_id, device_id, model, serial_number, drive_type, interface_type, size, partitions)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
            print("🔄 Inserting driver info into assets_drives_info table...")
            print(f"Total records to insert: {len(records)}")
            print("This may take a while...")
            if not records:
                print("❌ No records to insert.")
                return
            # Execute the insert query for all records
            print("Executing insert query...")
            records_fixed = [
                (json.dumps(rec[0]), *rec[1:]) for rec in records
            ]
            cursor.executemany(insert_query, records_fixed)
            connection.commit()
            print("✅ Driver info inserted successfully.")
            print(f"[+] Inserted {len(records)} records into assets_drives_info")
        except mysql.connector.Error as err:
            print(f"❌ MySQL error: {err}")
        except Exception as e:
            print(f"❌ General error: {e}")
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    def get_drive_info(self, asset_id):
        records = []
        for p in psutil.disk_partitions(all=False):
            device_path = p.device      # e.g. '/dev/sda1' (Linux/macOS) or 'C:\\' (Windows)
            mountpoint = p.mountpoint   # e.g. '/' or 'C:\\'

            try:
                usage = psutil.disk_usage(mountpoint)
                size = usage.total
            except Exception:
                size = 0

            system = platform.system()
            # For Linux/macOS: strip /dev/ prefix; for Windows: keep device as is
            if system in ('Linux', 'Darwin'):
                device_name = re.sub(r'^/dev/', '', device_path)
            else:  # Windows
                device_name = device_path

            print(f"Device: {device_name}, Mountpoint: {mountpoint}, Size: {size}")

            # Extract parent device name
            if device_name.startswith("nvme") and "p" in device_name:
                device_id = re.sub(r'p[0-9]+$', '', device_name)
            else:
                device_id = re.sub(r'[0-9]+$', '', device_name)

            platform_name = platform.system().lower()
            if platform_name == "windows":
                print("🔍 Collecting Windows system information...")
                drive_info = self.get_windows_drive_info(device_id)
            elif platform_name == "linux":
                print("🔍 Collecting Linux system information...")
                drive_info = self.get_mac_drive_info(device_id)
            elif platform_name == "darwin":  # macOS
                print("🔍 Collecting macOS system information...")
                drive_info = self.get_mac_drive_info(device_id) 
            else:
                print("❌ Unsupported platform:", platform_name)
                exit(1)
                
            if drive_info is None:
                continue  # skip loop/virtual

            records.append((
                asset_id,
                device_id,
                drive_info.get("model", "Unknown"),
                drive_info.get("serial_number", "Unknown"),
                drive_info.get("drive_type", "Unknown"),
                drive_info.get("interface_type", "Unknown"),
                size,
                device_name  # original partition name
            ))
        print(f"🔍 Collected drive information for {len(records)} devices.")
        if records:
            print(records)
            print("🔄 Inserting drive information into the database...")
            self.insert_driver_info(records)
