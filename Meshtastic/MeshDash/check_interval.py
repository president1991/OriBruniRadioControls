import time
from meshtastic.serial_interface import SerialInterface

# 1) Open the radio
iface = SerialInterface("COM5")

# 2) Give it a couple of seconds to fetch your local configs over the air
time.sleep(2)

# 3) Access the neighbor_info module's config using the moduleConfig attribute
neighbor_info_config = iface.localNode.moduleConfig.neighbor_info

# 4) Print your update_interval
print("neighbor_info.update_interval =", neighbor_info_config.update_interval)