"""
Municipalité des îles-de-la-Madeleine
Iohann Paquette
2024-06-18
"""

"""
Bibliothèques
"""
import time
from datetime import datetime
from pyhtcc import PyHTCC
import os
import schedule
import threading
import firebase_admin
from firebase_admin import credentials, db
import json
import pytz
import pandas as pd
import requests
import ssl

"""
Constantes
"""

DATABASE_URL = 'https://appmuniles-default-rtdb.firebaseio.com/'

cred = credentials.Certificate("./appmuniles-firebase-adminsdk-qp9zl-b94ab152f3.json")
default_app = firebase_admin.initialize_app(cred, {
    'databaseURL': DATABASE_URL
})

LONGITUDE = -61.750022
LATITUDE = 47.445642
TIMEZONE = 'America/Goose_Bay'
RELOG_TIME = 7200  # en secondes - 2h

"""
Classe
"""
class Collector:
    """
    Constructeur de notre classe
    """
    def __init__(self):
        self.user = None
        self.email = None
        self.mdp = None
        self.session = requests.Session()
        self.timer = None

        self.login()
        self.zones = self.user.get_all_zones()
        self.running = True
        self.list_threads = []

    def login(self):
        try:
            if not self.user:
                self.email = input('Votre courriel : ')
                self.mdp = input('Mot de passe : ')

                self.user = PyHTCC(self.email, self.mdp)
            else:

                self.user.session = self.session
                self.user.authenticate()
            print('Authentification réussie.')
            self.start_timer()

        except requests.exceptions.SSLError as ssl_error:
            print(f"SSL Error: {ssl_error}")
            with open("error_log.txt", "a") as file:
                file.write(f"SSL Error while login: {str(ssl_error)}\n")
            self.retry_login()

        except Exception as e:
            print(e)
            with open("error_log.txt", "a") as file:
                file.write(f"Error while login: {str(e)}\n")
            self.retry_login()

    def retry_login(self):
        print('Réessayer l\'authentification...')
        time.sleep(5)
        self.login()

    def start_timer(self):
        if self.timer:
            self.timer.cancel()
        self.timer = threading.Timer(RELOG_TIME - 300, self.login)
        self.timer.start()

    def run_schedule(self):
        try:
            while self.running:
                schedule.run_pending()
                time.sleep(1)
        except Exception as e:
            print(e)
            self.user.logout()
            self.cleanup_threads()

    def get_temperature(self):
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "current": "temperature_2m,relative_humidity_2m",
            "timezone": TIMEZONE
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            response = response.json()

            current = response['current']
            current_temperature_2m = current['temperature_2m']
            current_humidity_2m = current['relative_humidity_2m']

            return current_temperature_2m, current_humidity_2m

        except requests.RequestException as e:
            print(e)
            with open("error_log.txt", "a") as file:
                file.write(f"Error fetching data from Open-Meteo API: {str(e)}\n")
            return None

    def get_current_data(self, zone):
        zone.refresh_zone_info()
        zone_info = zone.zone_info
        latest_data = zone_info['latestData']
        ui_data = latest_data['uiData']
        fan_data = latest_data['fanData']

        return zone_info, ui_data, fan_data

    def get_data(self, zones):
        try:
            print('Veuillez choisir la récurrence des requêtes')
            print('-------------------------------------')
            print("1. MINUTES")
            print("2. HEURES")
            print("3. JOURS")
            print('-------------------------------------')

            option = int(input())
            every = int(input('Tous les (CHIFFRES) : '))

            while not 1 <= option <= 3:
                option = int(input('Réessayer:'))

            for zone in zones:
                if option == 1:
                    schedule.every(every).minutes.do(self.collect_data, zone)
                elif option == 2:
                    schedule.every(every).hours.do(self.collect_data, zone)
                elif option == 3:
                    schedule.every(every).days.do(self.collect_data, zone)

            schedule_thread = threading.Thread(target=self.run_schedule)
            schedule_thread.start()
            self.list_threads.append(schedule_thread)

            while self.running:
                cmd = input("Entrez STOP pour arrêter le programme\n")
                if cmd.strip().lower() == 'stop':
                    self.running = False
                    break

            print('Arrêt en cours...')
            self.cleanup_threads()
            self.user.logout()

        except Exception as e:
            utcmoment_naive = datetime.now(pytz.utc)
            with open("error_log.txt", "a") as file:
                file.write(f"{utcmoment_naive} - Erreur dans get_data: {str(e)}\n")
            self.user.logout()
            exit(1)

    def collect_data(self, zone):
        try:

            zone_info, ui_data, fan_data = self.get_current_data(zone)

            utcmoment_naive = datetime.now(pytz.utc)
            utcmoment = utcmoment_naive.replace(tzinfo=pytz.utc)

            timestamp = utcmoment.astimezone(pytz.timezone('America/Goose_Bay')).strftime("%Y-%m-%d %H:%M:%S")
            date = utcmoment.astimezone(pytz.timezone('America/Goose_Bay')).strftime("%Y-%m-%d")

            zone_name = zone_info['Name']
            device_id = zone.device_id

            temperature, humidity = self.get_temperature()

            data = {
                "device_id": device_id,
                "zone_name": zone_name,
                "timestamp": timestamp,
                "display_temperature": ui_data['DispTemperature'],
                "display_units": ui_data['DisplayUnits'],
                "outdoor_humidity": humidity,
                "outdoor_temperature": temperature,
                "heat_setpoint": ui_data['HeatSetpoint'],
                "cool_setpoint": ui_data['CoolSetpoint'],
                "fan_is_running": fan_data['fanIsRunning']
            }

            self.write_in_db(zone_name, device_id, date, data)
            print(f'Data collected for {device_id} - {zone_name} at {timestamp}')

        except Exception as e:
            with open("error_log.txt", "a") as file:
                file.write(f"Erreur dans collect_data : {str(e)}\n")
            self.user.logout()
            exit(1)

    def write_in_db(self, zone_name, device_id, date, data):
        try:
            ref = db.reference(f'/{device_id}/{zone_name}/{date}-THERMOSTAT_DATA')
            ref.push(data)
        except Exception as e:
            with open("error_log.txt", "a") as file:
                file.write(f"Erreur dans l'écriture de la base de données : {str(e)}\n")
            self.user.logout()
            exit(1)

    def get_all_zones(self):
        os.system('cls' if os.name == 'nt' else 'clear')

        print('Différentes localisations:')
        print('-------------------------------------')

        for i, zone in enumerate(self.zones, start=1):
            print(f"{i}\tZone ID: {zone.device_id} | Zone Name: {zone.zone_info['Name']}\n")

        choix = input('Affichez les infos des zones (séparer les numéros par une virgule) :')
        choix_indices = [int(index.strip()) for index in choix.split(',')]

        self.get_data([self.zones[i - 1] for i in choix_indices])

    def cleanup_threads(self):
        for t in self.list_threads:
            t.join()
        #self.list_threads.clear()

if __name__ == "__main__":
    try:
        c = Collector()
        c.get_all_zones()
    except Exception as e:
        with open("error_log.txt", "a") as file:
            file.write(f"Erreur dans le main : {str(e)}\n")
        print(e)
        exit(1)
