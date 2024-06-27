from flask import Flask, request, jsonify, Response
import threading
import os
import time
from datetime import datetime
from pyhtcc import PyHTCC
import schedule
from flask_cors import CORS
from flask_sse import sse

app = Flask(__name__)
CORS(app)

desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
FILENAME = os.path.join(desktop_path, datetime.today().strftime("%m_%d_%Y"))
collector = None

class Collector:
    def __init__(self, user):
        self.user = user
        self.zones = user.get_all_zones()
        self.running = True
        self.data_queue = []
        self.schedule_thread = None  # Ajouter une référence au thread
        self.lock = threading.Lock()

    def run_schedule(self):
        try:
            while self.running:
                schedule.run_pending()
                time.sleep(1)
        except Exception as e:
            print(e)
            print('Déconnexion...')
            self.user.logout()
            exit(1)

    def get_current_data(self, zone):
        zone.refresh_zone_info()
        
        zone_info = zone.zone_info
        latest_data = zone_info['latestData']
        ui_data = latest_data['uiData']
        fan_data = latest_data['fanData']

        return zone_info, ui_data, fan_data

    def collect_data(self, zone):
        zone_info, ui_data, fan_data = self.get_current_data(zone)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data = f"{zone.device_id},{zone_info['Name']},{timestamp},{ui_data['DispTemperature']},{ui_data['OutdoorTemperature']},{ui_data['DisplayUnits']},{ui_data['IndoorHumidity']},{ui_data['OutdoorHumidity']},{ui_data['HeatSetpoint']},{ui_data['CoolSetpoint']},{fan_data['fanIsRunning']}\n"
        with open(f"{FILENAME}.csv", "a") as file:
            file.write(data)
        print(f'Data collected at {timestamp}')

        with self.lock:
            self.data_queue.append(data)

    def get_all_zones(self, user):
        
        print('En recherche ...')
        zones_data = []
        for zone in self.zones:
            zone_info = {
                "id": zone.device_id,
                "name": zone.zone_info['Name']
            }
            zones_data.append(zone_info)

        return zones_data


@app.route('/connect', methods=['POST'])
def connect():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')

        global user
        user = PyHTCC(email, password)

        global collector
        collector = Collector(user)

        #getting all zones
        zones = collector.get_all_zones(user)
        
        return jsonify({"status": "connected","user":user.username,"zones":zones}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": "Failed to connect. Please check your credentials and try again."}), 401

@app.route('/start', methods=['POST'])
def start():
    global collector
    global user
    
    data = request.json
    choix = data.get('choix')
    frequency = data.get('frequency')
    frequency_type = data.get('frequency_type')
    print(choix)
    zone = collector.zones[choix]

    if frequency_type == "minutes":
        schedule.every(frequency).minutes.do(collector.collect_data, zone)
    elif frequency_type == "hours":
        schedule.every(frequency).hours.do(collector.collect_data, zone)
    elif frequency_type == "days":
        schedule.every(frequency).days.do(collector.collect_data, zone)
    
    collector.schedule_thread = threading.Thread(target=collector.run_schedule)
    collector.schedule_thread.start()

    return jsonify({"status": "started"}), 200

@app.route('/logout', methods=['POST'])
def logout():
    global user
    try:
        user.logout()
        time.sleep(1)
        return jsonify({"status": "loggedOut"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": "not able to logout"}), 401
    
@app.route('/events', methods=['GET'])
def stream_events():
    global event_source
    def generate():
        global collector
        while collector.running:
            with collector.lock:
                if collector.data_queue:
                    data = collector.data_queue.pop(0)
                    yield f"data:{data}\n\n"
                    time.sleep(1)
    try:
        event_source = Response(generate(), mimetype='text/event-stream')
        return event_source
    except Exception as e:
        print(f"Erreur lors de la création de l'EventSource: {e}")
        if event_source:
            event_source.close()
        return jsonify({"status": "error", "message": "Failed to create event source."}), 500

@app.route('/stop', methods=['POST'])
def stop_collecting():
    global collector
    global event_source
    try:
        collector.running = False
        print('Arrêt des threads en cours...')
        collector.schedule_thread.join()  # Attendre que le thread se termine proprement
        if event_source:
            event_source.close()
        return jsonify({"status": "stopped"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
if __name__ == "__main__":
    app.run(debug=True)