import os
import time
import shutil

# Define the directory where config files are generated
source_dir = "./configs"

# Define where each router's config should be copied
router_directories = {
    "i1": "./dynamips/ea02be46-eb1f-48d4-9352-33ca9413d0ec/configs",
    "i2": "./dynamips/cda283b6-56ee-4e6a-b2b7-535db98221d8/configs",
    "i3": "./dynamips/b59a874e-b595-404a-a58d-024c17df8056/configs",
    "i4": "./dynamips/aa451d58-3583-4592-9b14-79485b7a4bd2/configs",
    "i5": "./dynamips/34353479-520b-4294-9b79-dfafedb3831a/configs",
    "i6": "./dynamips/1b2243c4-cb56-4f7c-8098-5c3b4a914f2c/configs",
    # Add more routers here if needed
}

# Ensure all router directories exist
for path in router_directories.values():
    os.makedirs(path, exist_ok=True)

def move_config_files():
    """Moves config files from source directory to respective router directories"""
    files = os.listdir(source_dir)

    for file in files:
        if file.endswith("_startup-config.cfg"):  # Ensure it's a config file
            router_name = file.split("_")[0]  # Extract router name (e.g., "R1" from "R1_startup-config.cfg")

            if router_name in router_directories:
                src_path = os.path.join(source_dir, file)
                dest_path = os.path.join(router_directories[router_name], file)

                shutil.move(src_path, dest_path)
                print(f"✅ Moved {file} to {dest_path}")

# Run the bot continuously
print("🚀 Drag & Drop Bot Started! Watching for new config files...")


move_config_files()
    