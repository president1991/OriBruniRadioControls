# Meshtastic Raspberry Receiver

## Overview
This project sets up a Flask server on a Raspberry Pi to receive and display data from a Meshtastic mesh network. It provides a web interface to view recent messages and punches stored in a MySQL database, making it ideal for monitoring radio control data in real-time.

## Purpose
The Meshtastic Raspberry Receiver is designed to:
- Collect data from Meshtastic devices connected to the Raspberry Pi.
- Store this data in a local MySQL database for historical tracking.
- Serve a web dashboard to visualize recent messages and punch data in an accessible, user-friendly format.

## Features
- **Web Dashboard**: Displays recent messages and punches with a clean, modern interface.
- **Database Integration**: Stores data in MySQL for persistence and querying.
- **Real-Time Updates**: Automatically refreshes data every 5 seconds to show the latest information.

## Requirements
- Raspberry Pi (any model with network connectivity)
- Python 3.x
- MySQL Server (local or remote)
- Flask and Flask-SocketIO libraries
- Access to a Meshtastic mesh network (optional for database-only mode)

## Installation

### 1. Clone or Copy Files
Transfer the contents of this directory to your Raspberry Pi. You can use `scp` or manually copy the files to a directory like `/home/radiocontrol/RECEIVER`.

Example using `scp` from a local machine:
```bash
scp -r Meshtastic/Raspberry_RECEIVER/* radiocontrol@<Raspberry_Pi_IP>:/home/radiocontrol/RECEIVER/
```
Replace `<Raspberry_Pi_IP>` with the IP address of your Raspberry Pi.

### 2. Install Dependencies
Install the required Python packages. Due to potential externally managed environment restrictions on Raspberry Pi OS, you might need to use a virtual environment.

#### Option 1: Direct Installation (if permitted)
```bash
pip3 install flask flask-socketio mysql-connector-python --user
```

#### Option 2: Virtual Environment (recommended)
```bash
python3 -m venv /home/radiocontrol/RECEIVER/venv
/home/radiocontrol/RECEIVER/venv/bin/pip install flask flask-socketio mysql-connector-python
```

### 3. Configure Database Settings
Edit `config.ini` to set your MySQL database credentials under the `[mysql]` section. If the file does not exist or lacks the necessary section, the server will use default values which might need adjustment.

Example `config.ini`:
```ini
[mysql]
host = localhost
port = 3306
user = meshdash
password = your_password_here
database = OriBruniRadioControls
```

### 4. Run the Server
Start the Flask server to serve the web interface and fetch data from the database.

#### If using a virtual environment:
```bash
/home/radiocontrol/RECEIVER/venv/bin/python3 /home/radiocontrol/RECEIVER/server.py
```

#### If installed directly:
```bash
python3 /home/radiocontrol/RECEIVER/server.py
```

The server will run on port 5000 by default, accessible from any device on the same network.

### 5. Access the Web Interface
Open a web browser on any device connected to the same network as your Raspberry Pi and navigate to:
```
http://<Raspberry_Pi_IP>:5000
```
Replace `<Raspberry_Pi_IP>` with the IP address of your Raspberry Pi.

## Web Interface
- **Messaggi Recenti**: Displays recent messages with columns for Date, Type (TEL or PUNC), Nome Radio, Messaggio, Hops, RSSI, and SNR.
- **Punzonature Recenti**: Shows recent punch data with columns for Timestamp, Nome, PKey, Record ID, Control, Card Number, and Punch Time.
- The interface refreshes every 5 seconds to display the latest data from the database.

## Troubleshooting
- **Date Display Issues**: If the "Data" column shows incorrect values or "N/A", check the browser console (F12 -> Console) for logs about `data_ora` to debug the date format.
- **Database Connection Errors**: Ensure MySQL credentials in `config.ini` are correct and the database server is accessible from the Raspberry Pi.
- **Dependency Installation**: If `pip` installation fails due to an externally managed environment, use a virtual environment as described in the installation steps.
- **Server Not Starting**: Check for error messages in the terminal when running `server.py`. Common issues include missing dependencies or incorrect file paths.

## Customization
- **Web Interface**: Modify `templates/index.html` to adjust the layout or data display as needed.
- **Server Behavior**: Edit `server.py` to change data fetching logic or add new endpoints for additional functionality.

## License
This project is provided as-is for personal and educational use. Feel free to modify and distribute as needed for your specific requirements.

## Contact
For support or further customization, please contact the project maintainer or refer to the Meshtastic community for additional resources on mesh networking.
