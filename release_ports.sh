#!/bin/bash
# This script finds and kills processes that are using the serial ports needed by the application

# Define the port names to look for
MESHTASTIC_PORT="/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0"
SPORTIDENT_PORT="/dev/serial/by-id/usb-Silicon_Labs_SPORTident_USB_to_UART_Bridge_Controller_3958-if00-port0"

# Find the actual device files these symlinks point to
MESH_DEVICE=$(readlink -f "$MESHTASTIC_PORT" 2>/dev/null)
SPORT_DEVICE=$(readlink -f "$SPORTIDENT_PORT" 2>/dev/null)

echo "Looking for processes using Meshtastic port: $MESHTASTIC_PORT ($MESH_DEVICE)"
echo "Looking for processes using SportIdent port: $SPORTIDENT_PORT ($SPORT_DEVICE)"

# Find all processes using these ports
find_port_processes() {
    local PORT=$1
    local DEVICE=$2
    
    # Try multiple methods to find processes using the port
    echo "Checking processes for $PORT"
    
    # Method 1: Using fuser
    if command -v fuser &> /dev/null; then
        echo "Using fuser to find processes:"
        fuser -v $PORT 2>/dev/null
        fuser -v $DEVICE 2>/dev/null
    fi
    
    # Method 2: Using lsof
    if command -v lsof &> /dev/null; then
        echo "Using lsof to find processes:"
        lsof $PORT 2>/dev/null
        lsof $DEVICE 2>/dev/null
    fi
    
    # Method 3: Check for Python processes that might be using serial ports
    echo "Checking for Python processes that might be using serial ports:"
    ps aux | grep "[p]ython.*serial\|[m]eshtastic"
}

# Kill processes using these ports
kill_port_processes() {
    local PORT=$1
    local DEVICE=$2
    
    echo "Attempting to kill processes using $PORT or $DEVICE"
    
    # Kill using fuser
    if command -v fuser &> /dev/null; then
        fuser -k $PORT 2>/dev/null
        fuser -k $DEVICE 2>/dev/null
        echo "Used fuser to kill processes"
    fi
    
    # Look for Python processes that might be using Meshtastic
    echo "Killing Python processes that might be using meshtastic"
    pkill -f "python.*meshtastic"
    
    # Look for any serial_interface processes
    echo "Killing Python processes that might be using serial_interface"
    pkill -f "serial_interface"
    
    # Last resort: kill any read_serial.py instances except this script
    echo "Killing other read_serial.py instances"
    pkill -f "python.*read_serial.py"
}

# Display processes
echo "====== PROCESSES USING PORTS ======"
find_port_processes "$MESHTASTIC_PORT" "$MESH_DEVICE"
find_port_processes "$SPORTIDENT_PORT" "$SPORT_DEVICE"

# Ask for confirmation before killing
read -p "Do you want to kill these processes? (y/n): " confirm
if [[ $confirm == [yY] || $confirm == [yY][eE][sS] ]]; then
    kill_port_processes "$MESHTASTIC_PORT" "$MESH_DEVICE"
    kill_port_processes "$SPORTIDENT_PORT" "$SPORT_DEVICE"
    echo "Done. Waiting 2 seconds for ports to be released..."
    sleep 2
    echo "Ports should be available now. Run your script."
else
    echo "Operation cancelled."
fi