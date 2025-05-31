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

class GraphicsCardInfoCollector:
    
    def get_linux_graphics_info(self):
        graphics_info = []
        try:
            # Fetch basic graphics card info using lspci
            output = subprocess.check_output("lspci | grep VGA", shell=True).decode().strip()
            for line in output.split('\n'):
                parts = line.split(' ')
                if len(parts) >= 5:
                    name = ' '.join(parts[3:])
                    # Add other details as needed
                    graphics_info.append({
                        'name': name,
                        'adapter_compatibility': None,  # This can be extracted from other commands
                        'driver_version': None,         # Will use `lshw` or `glxinfo` to get this
                        'video_processor': None,        # Can be fetched via `lshw` or `glxinfo`
                        'current_horizontal_resolution': None,  # NULL for missing data, can be fetched later
                        'current_vertical_resolution': None,    # NULL for missing data, can be fetched later
                        'current_refresh_rate': None,  # NULL for missing data, can be fetched later
                        'adapter_ram': None,  # Can be checked with `lshw` or `lspci -v`
                        'availability': None,  # Example value, you may want to fill this in with other info
                        'status': None         # Example value, you may want to fill this in with other info
                    })
            
            # Fetch detailed graphics card info using lshw
            lshw_output = subprocess.check_output("sudo lshw -C display", shell=True).decode().strip()
            for line in lshw_output.split('\n'):
                if "configuration" in line:
                    # This part gives adapter RAM, driver version, and other details
                    if 'driver=' in line:
                        driver_version = line.split('driver=')[1].split()[0]
                    else:
                        driver_version = "Unknown"
                    
                    if 'memory=' in line:
                        adapter_ram = line.split('memory=')[1].split()[0]
                    else:
                        adapter_ram = "Unknown"
                        
                    # Example: Extracting adapter compatibility, video processor, and resolution (if available)
                    graphics_info[0]['adapter_compatibility'] = "Compatible"  # Placeholder
                    graphics_info[0]['driver_version'] = driver_version
                    graphics_info[0]['adapter_ram'] = adapter_ram
                    graphics_info[0]['video_processor'] = "NVIDIA"  # Example, should be extracted based on your hardware
                    
            # Fetch current horizontal/vertical resolution and refresh rate using xrandr
            xrandr_output = subprocess.check_output("xrandr | grep '*' | cut -d' ' -f4", shell=True).decode().strip()
            if xrandr_output:
                resolution = xrandr_output.split('x')
                graphics_info[0]['current_horizontal_resolution'] = resolution[0]
                graphics_info[0]['current_vertical_resolution'] = resolution[1]
                # The refresh rate can be extracted from the same output (if available)
                graphics_info[0]['current_refresh_rate'] = "60"  # Assuming 60Hz if not found (can be extracted more accurately)
        except Exception as e:
            print("Error collecting graphics info on Linux:", e)        
        return graphics_info

    def get_windows_graphics_info(self):
        graphics_info = []
        try:
            # Use wmic to get graphics info (works on most Windows systems)
            output = subprocess.check_output(
                'wmic path win32_videocontroller get Name,AdapterCompatibility,AdapterRAM,DriverVersion,VideoProcessor,CurrentHorizontalResolution,CurrentVerticalResolution,CurrentRefreshRate,Status /format:list',
                shell=True
            ).decode(errors='ignore')

            # Split by two newlines to separate cards
            controllers = [c.strip() for c in output.split('\n\n') if c.strip()]
            for ctrl in controllers:
                info = {}
                lines = ctrl.strip().split('\n')
                for line in lines:
                    if '=' in line:
                        k, v = line.split('=', 1)
                        info[k.strip()] = v.strip() if v.strip() != '' else None
                if 'Name' in info:
                    graphics_info.append({
                        'name': info.get('Name'),
                        'adapter_compatibility': info.get('AdapterCompatibility'),
                        'driver_version': info.get('DriverVersion'),
                        'video_processor': info.get('VideoProcessor'),
                        'current_horizontal_resolution': info.get('CurrentHorizontalResolution'),
                        'current_vertical_resolution': info.get('CurrentVerticalResolution'),
                        'current_refresh_rate': info.get('CurrentRefreshRate'),
                        'adapter_ram': info.get('AdapterRAM'),
                        'availability': None,  # Not directly available in wmic
                        'status': info.get('Status'),
                    })
        except Exception as e:
            print("Error collecting graphics info on Windows:", e)
        return graphics_info

    def get_mac_graphics_info(self):
        graphics_info = []
        try:
            output = subprocess.check_output(
                ['system_profiler', 'SPDisplaysDataType'],
                text=True
            )
            # Find all GPU blocks
            gpu_block_pattern = re.compile(r'(Chipset Model:|Model:)([\s\S]+?)(?=\n\S|$)', re.MULTILINE)
            gpu_blocks = gpu_block_pattern.findall(output)

            for prefix, block in gpu_blocks:
                name_match = re.match(r"(?:Chipset Model:|Model:)\s*(.+)", prefix + block.splitlines()[0])
                name = name_match.group(1).strip() if name_match else None

                vendor = re.search(r'Vendor: (.+)', block)
                vram = re.search(r'VRAM.*: (.+)', block)
                driver_version = re.search(r'Metal.*: (.+)', block)
                resolution = re.search(r'Resolution: (\d+) x (\d+)', block)
                status = re.search(r'Status: (.+)', block)

                graphics_info.append({
                    'name': name if name else None,
                    'adapter_compatibility': vendor.group(1) if vendor else None,
                    'driver_version': driver_version.group(1) if driver_version else None,
                    'video_processor': None,  # Always None
                    'current_horizontal_resolution': resolution.group(1) if resolution else None,
                    'current_vertical_resolution': resolution.group(2) if resolution else None,
                    'current_refresh_rate': None,  # Always None
                    'adapter_ram': vram.group(1) if vram else None,
                    'availability': None,  # Always None
                    'status': status.group(1) if status else None
                })

            # If no GPU blocks found, return empty
            if not graphics_info:
                return []
        except Exception as e:
            print("Error collecting graphics info on macOS:", e)
            return []

        return graphics_info

    @staticmethod
    def insert_graphics_info(records):
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
                INSERT INTO assets_graphics_card_info
                (asset_id, name, adapter_compatibility, driver_version, video_processor, 
                current_horizontal_resolution, current_vertical_resolution, current_refresh_rate, 
                adapter_ram, availability, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
            print("🔄 Inserting driver info into assets_graphics_card_info table...")
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

    def get_graphics_card_info(self, asset_id):
        records = []
        print("✅ Running graphics_card_info_collector.py...")
        platform_name = platform.system().lower()
        if platform_name == "windows":
            print("🔍 Collecting Windows system information...")
            graphics_info = self.get_windows_graphics_info()
        elif platform_name == "linux":
            print("🔍 Collecting Linux system information...")
            graphics_info = self.get_linux_graphics_info()
        elif platform_name == "darwin":  # macOS
            print("🔍 Collecting macOS system information...")
            graphics_info = self.get_mac_graphics_info() 
        else:
            print("❌ Unsupported platform:", platform_name)
            exit(1)
        print(f"✅ Graphics card information collected successfully.{graphics_info}")
        # Collect the actual graphics card data and append to records
        for device_info in graphics_info:
            records.append((
                asset_id,
                device_info['name'],
                device_info['adapter_compatibility'],
                device_info['driver_version'],
                device_info['video_processor'],
                device_info['current_horizontal_resolution'],  # Can be NULL
                device_info['current_vertical_resolution'],    # Can be NULL
                device_info['current_refresh_rate'],  # Can be NULL
                device_info['adapter_ram'],  # Can be NULL
                device_info['availability'],  # Can be NULL
                device_info['status']         # Can be NULL
            ))

        if records:
            self.insert_graphics_info(records)
