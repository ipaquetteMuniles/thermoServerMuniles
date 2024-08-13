"""
Municipalité des îles-de-la-Madeleine
Iohann Paquette
2024-06-18
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
from threading import Lock

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
RELOG_TIME = 14400  # en secondes - 4h
MAX_RETRY_ATTEMPTS = 5
RETRY_BACKOFF_TIME = 5  # en secondes

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
        self.session = None
        self.timer = None
        self.running = True
        self.list_threads = []
        self.file_lock = Lock()
        self.session_lock = Lock()
        self.retries = 0

        self.login()
        self.load_cookies()

    def log_error(self, message):
        with self.file_lock:
            with open("error_log.txt", "a") as file:
                file.write(f"{time.asctime(time.localtime())} - {message}\n")

    def save_cookies(self):
        try:
            with open("session_cookies.pkl", "wb") as file:
                cookies_dict = cookiejar_to_dict(self.session.cookies)
                pickle.dump(cookies_dict, file)
        except Exception as e:
            self.log_error(f"Erreur lors de save_cookies : {str(e)}")

    def load_cookies(self):
        if os.path.exists("session_cookies.pkl") and os.path.getsize("session_cookies.pkl") > 0:
            try:
                with open("session_cookies.pkl", "rb") as file:
                    cookies_dict = pickle.load(file)
                    self.session.cookies = dict_to_cookiejar(cookies_dict)
            except (EOFError, pickle.PickleError) as e:
                print("Le fichier de cookies est vide ou corrompu. Procédure sans chargement des cookies.")
                self.log_error(f"Erreur lors de load_cookies : {str(e)}")
            except Exception as e:
                print('Erreur lors de load_cookies :', e)
                self.log_error(f"Erreur lors de load_cookies : {str(e)}")
        else:
            print("Le fichier de cookies est vide. Procédure sans chargement des cookies.")

    def login(self):
        try:
            print("Starting login process...")
            self.session = requests.Session()

            if self.user is None:
                self.email = safe_input('Votre courriel : ')
                self.mdp = safe_input('Mot de passe : ')
                print(f"Email: {self.email}, Password: [hidden]")
                self.user = PyHTCC(self.email, self.mdp)

            if self.user.session.cookies is not None and self.session.cookies is not None:
                print("Setting session cookies...")
                self.session.cookies = self.user.session.cookies
                self.save_cookies()

            print('Authentification réussie.')
            self.zones = self.user.get_all_zones()
            self.start_timer()

        except requests.exceptions.SSLError as ssl_error:
            print(f"Erreur SSL : {ssl_error}")
            self.log_error(f"{time.asctime(time.localtime())} - Erreur SSL lors de la connexion : {str(ssl_error)}\n")
            self.retry_login()

        except Exception as e:
            print(f"Erreur lors de la connexion : {e}")
            self.log_error(f"Erreur lors de la connexion : {str(e)}\n")
            self.retry_login()

    def retry_login(self):
        with self.session_lock:
            self.user.logout()
            self.user = None

            if self.retries < MAX_RETRY_ATTEMPTS:
                self.retries += 1
                print(f"Réessayer l'authentification dans {RETRY_BACKOFF_TIME * self.retries} secondes...")
                time.sleep(RETRY_BACKOFF_TIME * self.retries)
                self.login()
            else:
                print("Nombre maximal de tentatives atteint. Abandon.")
                self.running = False

    def start_timer(self):
        with self.session_lock:
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
            print(f"Erreur dans run_schedule : {e}")
            self.log_error(f"Erreur dans run_schedule : {str(e)}")
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
            current = response.json()['current']

            current_temperature_2m = current['temperature_2m']
            current_humidity_2m = current['relative_humidity_2m']

            return current_temperature_2m, current_humidity_2m

        except requests.RequestException as e:
            print(f"Erreur lors de la requête API : {e}")
            self.log_error(f"Erreur lors de la requête API Open-Meteo : {str(e)}")
            return None, None

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

        except Exception as e:
            self.log_error(f"Erreur dans get_data : {str(e)}")

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
            print(f'Données collectées pour {device_id} - {zone_name}')

        except Exception as e:
            self.log_error(f"Erreur dans collect_data : {str(e)}")

    def write_in_db(self, zone_name, date, data):
        try:
            ref = db.reference(f'/{zone_name}/{date}-THERMOSTAT_DATA')
            ref.push(data)
        except Exception as e:
            self.log_error(f"{time.asctime(time.localtime())} - Erreur lors de l'écriture dans la base de données : {str(e)}\n")

    def cleanup_threads(self):
        self.running = False
        for thread in self.list_threads:
            if thread.is_alive():
                thread.join()

    def shutdown(self):
        self.cleanup_threads()
        self.user.logout()
        self.save_cookies()
        self.log_error('Arret du programme')
        print("Arrêt complet du programme.")

    def get_all_zones(self):
        """
        Display available zones and prompt the user to select zones for data collection.
        """
        try:
            os.system('cls' if os.name == 'nt' else 'clear')

            print('Différentes localisations:')
            print('-------------------------------------')

            for i, zone in enumerate(self.zones, start=1):
                print(f"{i}\tZone ID: {zone.device_id} | Zone Name: {zone.zone_info['Name']}\n")

            choix = safe_input('Affichez les infos des zones (séparer par une virgule). Ex : 1, 3: ')
            zones_selected = [self.zones[int(idx.strip()) - 1] for idx in choix.split(',')]

            self.get_data(zones_selected)

        except Exception as e:
            self.log_error(f"Erreur dans get_all_zones: {str(e)}")
            self.shutdown()

if __name__ == "__main__":
    """
    Main function to initialize and run the data collection process.
    """
    collector = Collector()

    try:
        collector.get_all_zones()
    except KeyboardInterrupt:
        print("\nInterruption du programme par l'utilisateur.")
        collector.shutdown()
    except Exception as e:
        collector.log_error(f"Erreur non gérée : {str(e)}")
        collector.shutdown()