import os
import sys
import mysql.connector
import socket
import subprocess
import platform
import shutil

from src.lib.hardware_info_collector import HardwareInfoCollector
from src.lib.drive_info_collector import DriveInfoCollector
from src.lib.graphics_card_info_collector import GraphicsCardInfoCollector
from src.lib.memory_info_collector import MemHardwareInfoCollector
from src.lib.network_adapter_info_collector import NetworkAdapterInfoCollector


# Database config (store securely in production!)
DB_HOST="68.178.156.243"
DB_USER="itamcloud"
DB_PASSWORD="Kgl0b@ltech"
DB_NAME="ITAMCloud"


def check_serial_no(serial_number):
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

        # Get asset id and company_id from assets table using the given serial_number
        asset_id_query = "SELECT id, company_id FROM assets WHERE serial = %s"
        cursor.execute(asset_id_query, (serial_number,))
        asset_row = cursor.fetchone()
        if not asset_row:
            print(f"❌ No asset found for serial_number: {serial_number}")
            return None
        asset_id, company_id = asset_row
        connection.commit()
        print(f"✅ Found asset_id: {asset_id}, company_id: {company_id} for serial_number: {serial_number}")
        # Store both in a tuple (or dict as needed) and return
        asset_info = (asset_id, company_id)
        return asset_info

    except mysql.connector.Error as err:
        print(f"❌ MySQL error: {err}")
    except Exception as e:
        print(f"❌ General error: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
            
def main():
    company_id = None
    serial = None
    try:
        serial = input("Please enter the serial: ")
    except ValueError:
        print("Invalid input. serial must be given.")
        exit(1)
    print("You entered serial:", serial)
    asset_info = check_serial_no(serial)
    if asset_info:
        asset_id, company_id = asset_info
        print(f"Asset ID: {asset_id}, Company ID: {company_id}")
    else:
        print("No asset found with the provided serial number.")
        exit(1)
    hardware_collector = HardwareInfoCollector(company_id, asset_id)
    drive_collector = DriveInfoCollector()
    graphics_collector = GraphicsCardInfoCollector()
    mac_hardware_collector = MemHardwareInfoCollector(company_id, asset_id)
    network_collector = NetworkAdapterInfoCollector(company_id, asset_id)
    # Collecting information
    hardware_collector.get_system_info()
    drive_collector.get_drive_info(asset_id)
    graphics_collector.get_graphics_card_info(asset_id)
    mac_hardware_collector.get_memnory_info()
    network_collector.get_network_info()
    print("Drive information collection completed.")

def check_internet(host="8.8.8.8", port=53, timeout=3):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error:
        return False


def check_python_installed():
    system = platform.system()
    python_commands = ["python3", "python"]

    # Try to find python in PATH using shutil.which (cross-platform)
    for cmd in python_commands:
        path = shutil.which(cmd)
        if path:
            print(f"✅ {cmd} found at: {path}")
            return True

    # As a fallback, try to invoke the python command and check for errors
    for cmd in python_commands:
        try:
            result = subprocess.run(
                [cmd, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            if result.returncode == 0 or "Python" in result.stdout or "Python" in result.stderr:
                print(f"✅ {cmd} is installed: {result.stdout or result.stderr}")
                return True
        except Exception:
            continue

    print("❌ Python is not installed or not found in PATH.")
    return False


if __name__ == "__main__":
    if not check_internet():
        print("No internet connection.")
        sys.exit(1)
    check_python_installed()
    main()
