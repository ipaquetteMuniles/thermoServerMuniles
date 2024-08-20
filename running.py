import os
import subprocess
import psutil
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

SCRIPT_NAME = 'CollectData.py'
STATUS_FILE = '/home/Iohann/CollectData.status'

def is_script_running():
    """Check if the script is running by searching for the status file."""
    if os.path.isfile(STATUS_FILE):
        with open(STATUS_FILE, 'r') as file:
            lines = file.readlines()
        if len(lines) == 2:
            pid = int(lines[0].strip())
            status = lines[1].strip()
            if status == 'running' and psutil.pid_exists(pid):
                process = psutil.Process(pid)
                cmdline = process.cmdline()
                # Debugging print
                print(f"Process command line: {cmdline}")
                if process.is_running() and (SCRIPT_NAME in cmdline or os.path.abspath(SCRIPT_NAME) in cmdline):
                    print(f"Script {SCRIPT_NAME} is running with PID {pid}")
                    return True
                else:
                    print(f"Script is not running or cmdline doesn't match. Expected: {SCRIPT_NAME}")
            else:
                print(f"Status file content is incorrect or PID does not exist: PID={pid}, Status={status}")
        else:
            print("Status file does not have the expected format.")

    # Clean up the status file if it exists but the process isn't running
    if os.path.isfile(STATUS_FILE):
        os.remove(STATUS_FILE)
        print(f"Removed stale status file: {STATUS_FILE}")

    return False

def start_script():
    """Start the script and create a status file with PID and status."""
    script_path = os.path.abspath(SCRIPT_NAME)
    try:
        process = subprocess.Popen(['python', script_path])
        with open(STATUS_FILE, 'w') as file:
            file.write(f"{process.pid}\n")
            file.write('running')
        print(f"Started script with PID: {process.pid}")
        return jsonify({"message": f"Started script with PID {process.pid}"}), 200
    except Exception as e:
        print(f"Failed to start script: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/stop', methods=['POST'])
def stop_script():
    """Stop the running script and remove the status file."""
    print('Attempting to stop the script...')
    if os.path.isfile(STATUS_FILE):
        with open(STATUS_FILE, 'r') as file:
            lines = file.readlines()
        if len(lines) == 2:
            pid = int(lines[0].strip())
            try:
                process = psutil.Process(pid)
                process.terminate()  # or process.kill() for a more forceful stop
                process.wait()  # Wait for the process to terminate
                os.remove(STATUS_FILE)  # Remove the status file after stopping the process
                print(f"Stopped script with PID: {pid}")
                return jsonify({"message": f"Stopped script with PID {pid}"}), 200
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                print(f"No process found or error stopping process: {e}")
                return jsonify({"error": "No such process or access denied"}), 404
        else:
            print("Status file does not have the expected format.")
            return jsonify({"error": "Status file format is incorrect"}), 500
    else:
        print("No status file found. The script might not be running.")
        return jsonify({"error": "No status file found"}), 404

@app.route('/get_status', methods=['GET'])
def get_status():
    if is_script_running():
        return jsonify({"message": f"{SCRIPT_NAME} is running."}), 205
    else:
        return jsonify({"message": f"{SCRIPT_NAME} is not running."}), 206

@app.route('/start', methods=['POST'])
def main():
    """Start the script if it's not already running."""
    if is_script_running():
        return jsonify({"message": f"{SCRIPT_NAME} is already running."}), 200
    else:
        return start_script()
@app.route('/', methods=['GET'])
def index():
    return 'Hello'