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
STATUS_FILE = '/home/Iohann/Collector.status'

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
        self.file_lock = Lock()
        self.session_lock = Lock()
        self.running = True
        self.list_threads = []
        self.retries = 0
        self.email, self.mdp = self.get_credentials()
        self.user = None
        self.session = None
        self.timer = None

    def get_credentials(self):
        secrets = {}
        with open('credentials.txt','r') as file:
            for line in file:
                key, value = line.strip().split('=', 1)
                secrets[key] = value
        return secrets.get('email'), secrets.get('password')

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

            print(f"Email: {self.email}")

            string_password = '*' * len(self.mdp)
            print(f"Password:{string_password}")

            if self.user is None:
                print("Creation de l'utilisateur...")
                self.user = PyHTCC(self.email, self.mdp)

            if self.user.session.cookies is not None and self.session.cookies is not None:
                print("Setting session cookies...")
                self.session.cookies = self.user.session.cookies
                self.save_cookies()

            print('Authentification réussie.')
            self.load_cookies()

            self.start_timer()
            self.get_all_zones()

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
        try:
            self.ensure_authenticated()
            zone.refresh_zone_info()
            zone_info = zone.zone_info
            latest_data = zone_info['latestData']
            ui_data = latest_data['uiData']
            fan_data = latest_data['fanData']

            return zone_info, ui_data, fan_data
        except requests.exceptions.SSLError as ssl_error:
            print(f"Erreur SSL lors de get_current_data: {ssl_error}")
            self.log_error(f"Erreur SSL lors de get_current_data : {str(ssl_error)}")
            return None, None, None  # Return None to indicate an error
        except Exception as e:
            self.log_error(f"Erreur dans get_current_data : {str(e)}")
            return None, None, None  # Return None to indicate an error


    def get_data(self, zone):
        try:
            # tous les cinq minutes
            schedule.every(5).minutes.do(self.collect_data, zone)

            schedule_thread = threading.Thread(target=self.run_schedule)
            schedule_thread.start()
            self.list_threads.append(schedule_thread)

        except Exception as e:
            self.log_error(f"Erreur dans get_data : {str(e)}")

    def collect_data(self, zone):
        try:
            zone_info, ui_data, fan_data = self.get_current_data(zone)

            # Check if data fetching was unsuccessful
            if zone_info is None or ui_data is None or fan_data is None:
                print(f"Data collection failed for {zone.device_id} - {zone.zone_info['Name']}")
                return

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
            print(f'\nDonnées collectées pour {device_id} - {zone_name}')

        except Exception as e:
            self.log_error(f"Erreur dans collect_data : {str(e)}")
            self.retry_login()

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
        try:
            if os.path.exists(STATUS_FILE):
                os.remove(STATUS_FILE)
        except Exception as e:
            self.log_error(f"Erreur lors de la suppression du fichier de statut : {str(e)}")
        exit(1)


    def get_all_zones(self):
        """
        Display available zones and prompt the user to select zones for data collection.
        """
        self.zones = self.user.get_all_zones()

        try:
            print('Différentes localisations:')
            print('-------------------------------------')

            for zone in self.zones:
                print(f"\tZone ID: {zone.device_id} | Zone Name: {zone.zone_info['Name']}\n")
                self.get_data(zone)

        except Exception as e:
            self.log_error(f"Erreur dans get_all_zones: {str(e)}")
            self.retry_login()

if __name__ == "__main__":
    collector = Collector()

    try:
        with open(STATUS_FILE, 'w') as f:
            f.write(f"{os.getpid()}\n")
        collector.login()
    except KeyboardInterrupt:
        print("\nInterruption du programme par l'utilisateur.")
        collector.shutdown()
    except Exception as e:
        collector.log_error(f"Erreur non gérée : {str(e)}")
        collector.shutdown()
    finally:
        # Ensure STATUS_FILE is removed on shutdown
        if os.path.exists(STATUS_FILE):
            try:
                os.remove(STATUS_FILE)
            except Exception as e:
                collector.log_error(f"Erreur lors de la suppression du fichier de statut : {str(e)}")
