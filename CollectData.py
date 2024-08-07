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
import sys
import pickle

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

def cookiejar_to_dict(cookiejar):
    cookies = {}
    for cookie in cookiejar:
        cookies[cookie.name] = cookie.value
    return cookies

def dict_to_cookiejar(cookies):
    cookiejar = requests.cookies.RequestsCookieJar()
    for name, value in cookies.items():
        cookiejar.set(name, value)
    return cookiejar

def safe_input(prompt):
    if sys.stdin.isatty():
        return input(prompt)
    else:
        print(prompt)
        return sys.stdin.read().strip()

"""
Classe
"""
class Collector:
    """
    Constructeur de notre classe
    """
    def __init__(self):
        self.email = None
        self.mdp = None
        self.user = None
        self.session = requests.Session()
        self.timer = None
        self.running = True
        self.list_threads = []
        self.file = open("error_log.txt", "a")

        self.load_cookies()
        self.login()

    def save_cookies(self):
        with open("session_cookies.pkl", "wb") as file:
            cookies_dict = cookiejar_to_dict(self.session.cookies)
            pickle.dump(cookies_dict, file)

    def load_cookies(self):
        if os.path.exists("session_cookies.pkl") and os.path.getsize("session_cookies.pkl") > 0:
            try:
                with open("session_cookies.pkl", "rb") as file:
                    cookies_dict = pickle.load(file)
                    self.session.cookies = dict_to_cookiejar(cookies_dict)
            except EOFError:
                print("Le fichier de cookies est vide ou corrompu. Procédure sans chargement des cookies.")
        else:
            print("Le fichier de cookies est vide. Procédure sans chargement des cookies.")

    def login(self):
        try:
            if self.user is None:
                self.email = safe_input('Votre courriel : ')
                self.mdp = safe_input('Mot de passe : ')
                self.user = PyHTCC(self.email, self.mdp)

            if self.user.session.cookies:
                self.session.cookies = self.user.session.cookies
                self.save_cookies()

            print('Authentification réussie.')
            self.zones = self.user.get_all_zones()
            self.start_timer()

        except requests.exceptions.SSLError as ssl_error:
            print(f"Erreur SSL : {ssl_error}")
            self.file.write(f"{time.asctime(time.localtime())} - Erreur SSL lors de la connexion : {str(ssl_error)}\n")
            self.retry_login()

        except Exception as e:
            print(f"Erreur lors de la connexion : {e}")
            self.file.write(f"Erreur lors de la connexion : {str(e)}\n")
            self.retry_login()

    def retry_login(self):
        self.user.logout()
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
            self.file.write(f"{time.asctime(time.localtime())} - Error fetching data from Open-Meteo API: {str(e)}\n")
            return None
    def ensure_authenticated(self):
        if not self.user.session or not self.user.session.cookies:
            self.login()

    def get_current_data(self, zone):
        self.ensure_authenticated()

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

            option = int(safe_input('Option: '))
            every = int(safe_input('Tous les (CHIFFRES) : '))

            while not 1 <= option <= 3:
                option = int(safe_input('Réessayer: '))

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
                cmd = safe_input("Entrez STOP pour arrêter le programme\n")
                if cmd.strip().lower() == 'stop':
                    self.running = False
                    break

            print('Arrêt en cours...')
            self.cleanup_threads()
            self.user.logout()
            self.file.close()

        except Exception as e:
            utcmoment_naive = datetime.now(pytz.utc)
            with open("error_log.txt", "a") as self.file:
                self.file.write(f"{utcmoment_naive} - Erreur dans get_data: {str(e)}\n")

    def collect_data(self, zone):
        try:
            zone_info, ui_data, fan_data = self.get_current_data(zone)

            utcmoment_naive = datetime.now(pytz.utc)
            utcmoment = utcmoment_naive.replace(tzinfo=pytz.utc)

            timestamp = utcmoment.astimezone(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S")
            date = utcmoment.astimezone(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d")

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

            self.write_in_db(zone_name, date, data)
            print(f'Données collectées pour {device_id} - {zone_name} à {timestamp}')

        except Exception as e:
            self.file.write(f"{time.asctime(time.localtime())} - Erreur dans collect_data : {str(e)}\n")

    def write_in_db(self, zone_name, date, data):
        try:
            ref = db.reference(f'/{zone_name}/{date}-THERMOSTAT_DATA')
            ref.push(data)
        except Exception as e:
            self.file.write(f"{time.asctime(time.localtime())} - Erreur lors de l'écriture dans la base de données : {str(e)}\n")

    def get_all_zones(self):
        os.system('cls' if os.name == 'nt' else 'clear')

        print('Différentes localisations:')
        print('-------------------------------------')

        for i, zone in enumerate(self.zones, start=1):
            print(f"{i}\tZone ID: {zone.device_id} | Zone Name: {zone.zone_info['Name']}\n")

        choix = safe_input('Affichez les infos des zones (séparer par une virgule). Ex : 1, 3: ')
        zones_selected = [self.zones[int(idx.strip()) - 1] for idx in choix.split(',')]

        self.get_data(zones_selected)

    def cleanup_threads(self):
        self.running = False
        for thread in self.list_threads:
            thread.join()

if __name__ == "__main__":
    collector = Collector()
    collector.get_all_zones()
