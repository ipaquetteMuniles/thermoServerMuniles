"""
Municipalité des îles-de-la-Madeleine
Iohann Paquette
2024-06-18
"""

"""
Bibliothèques
"""
import time
from datetime import datetime, timedelta
from pyhtcc import PyHTCC
import os
import schedule
import threading
import firebase_admin
from firebase_admin import credentials,db
import json
import pytz
import requests
import pandas as pd
"""
Constantes
"""

DATABASE_URL = 'https://appmuniles-default-rtdb.firebaseio.com/'

cred = credentials.Certificate("./appmuniles-firebase-adminsdk-qp9zl-b94ab152f3.json")
default_app = firebase_admin.initialize_app(cred, {
	'databaseURL':DATABASE_URL
})

LONGITUDE = -61.750022
LATITUDE = 47.445642
TIMEZONE = 'America/Goose_Bay'

"""
Classe
"""
class Collector:
    """
    Fonctions
    """

    """
    Constructeur de notre classe
    """
    def __init__(self):
        
        self.user = None
        self.email = None
        self.mdp = None
        #authentification
        self.login()

        self.zones = self.user.get_all_zones()
        self.timeRunning = None
        self.running = True  # Flag to control the main loop

    def login(self):
        if self.email is None or self.mdp is None:
            self.email = input('Votre courriel : ')
            self.mdp = input('Mot de passe : ')

        print('Authentification...')

        # Authentification
        self.user = PyHTCC(self.email, self.mdp)

    def run_schedule(self):
        try:
            self.timeRunning = time.perf_counter()
            while self.running:
                schedule.run_pending()
                time.sleep(1)
        except Exception as e:
            input()
            print(e)
            print('Déconnexion...')
            self.user.logout()

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

            # Process hourly data
            current = response['current']
            current_temperature_2m = current['temperature_2m']
            current_humidity_2m = current['relative_humidity_2m']
            # Get the latest temperature

            return (current_temperature_2m,current_humidity_2m)

        except requests.RequestException as e:
            with open(f"error_log.txt", "w") as file:
                file.write(f"Error fetching data from Open-Meteo API: {str(e)}\n")
            return None

    def get_current_data(self, zone):
        zone.refresh_zone_info()

        zone_info = zone.zone_info
        latest_data = zone_info['latestData']
        ui_data = latest_data['uiData']
        fan_data = latest_data['fanData']

        return zone_info, ui_data, fan_data

    def get_data(self, zone):
        try:

            print('Veuillez choisir la recurrence des requetes')
            print('-------------------------------------')
            print("1. MINUTES")
            print("2. HEURES")
            print("3. JOURS")
            print('-------------------------------------')

            option = int(input())
            every = int(input('Tous les (CHIFFRES) : '))

            while not 1 <= option <= 3:
                option = int(input('Reessayer:'))

            if option == 1:
                schedule.every(every).minutes.do(self.collect_data, zone)
            elif option == 2:
                schedule.every(every).hours.do(self.collect_data, zone)
            elif option == 3:
                schedule.every(every).days.do(self.collect_data, zone)

            print("Écriture des données NE PAS FERMER LE PROGRAMME ...")
            # Start a new thread for the schedule
            schedule_thread = threading.Thread(target=self.run_schedule)
            schedule_thread.start()

            # Wait for the user to input 'stop' to stop the program
            while True:
                cmd = input("Entree 'stop' pour arreter le program: \n")
                if cmd.strip().lower() == 'stop':
                    self.running = False
                    break
            print('arret en cours...')
            schedule_thread.join()
            self.user.logout()

        except Exception as e:
            with open(f"error_log.txt", "w") as file:
                file.write(f"Erreur dans get_data: {str(e)}\n")
            self.user.logout()

    def collect_data(self, zone):
        try:

            now = time.perf_counter()
            time_to_log = now - self.timeRunning
            
            #Time to relog after 2h (7200 s)
            if time_to_log >= 120:#7200
                self.login()
                self.timeRunning = time.perf_counter()
            
            zone_info, ui_data, fan_data = self.get_current_data(zone)

            utcmoment_naive = datetime.now(pytz.utc)
            utcmoment = utcmoment_naive.replace(tzinfo=pytz.utc)

            #changment pour les îles de la madeleine
            timestamp = utcmoment.astimezone(pytz.timezone('America/Goose_Bay')).strftime("%Y-%m-%d %H:%M:%S")
            date = utcmoment.astimezone(pytz.timezone('America/Goose_Bay')).strftime("%Y-%m-%d")

            zone_name = zone_info['Name']
            device_id = zone.device_id

            temperature,humidity = self.get_temperature()

            data = {
                "device_id": device_id,
                "zone_name": zone_name,
                "timestamp": timestamp,
                "display_temperature": ui_data['DispTemperature'],
                "display_units": ui_data['DisplayUnits'],
                "outdoor_humidity": humidity,
                "outdoor_temperature":temperature,
                "heat_setpoint": ui_data['HeatSetpoint'],
                "cool_setpoint": ui_data['CoolSetpoint'],
                "fan_is_running": fan_data['fanIsRunning']
            }

            self.write_in_db(zone_name,device_id,date,data)
            print(f'Data collected at {timestamp}')

        except Exception as e:
            with open(f"error_log.txt", "w") as file:
                file.write(f"Erreur dans collect_data : {str(e)}\n")
            self.user.logout()

    def write_in_db(self,zone_name,device_id,date,data):
        try:
            ref = db.reference(f'/{device_id}/{zone_name}/{date}-THERMOSTAT_DATA')
            ref.push(data)
        except Exception as e:
            with open(f"error_log.txt", "w") as file:
                file.write(f"Erreur dans l'écriture de la base de données : {str(e)}\n")
            self.user.logout()

    def get_all_zones(self):
        os.system('cls' if os.name == 'nt' else 'clear')

        print('En recherche ...')
        zones = self.user.get_all_zones()

        print('Différentes localisations:')
        print('-------------------------------------')

        for i, zone in enumerate(zones, start=1):
            print(f"{i}\tZone ID: {zone.device_id} | Zone Name: {zone.zone_info['Name']}\n")

        choix = int(input('Affichez les infos de la zone # :'))

        while not 1 <= choix <= len(zones):
            print('Réessayer...')
            choix = int(input('Affichez les infos de la zone # :'))

        return zones[choix - 1]


if __name__ == "__main__":

    try:
    
        # Création du collecteur de données
        c = Collector()
        # Retour de la zone qu'on désire obtenir les données
        zone = c.get_all_zones()

        c.get_data(zone)

    except Exception as e:
        print(e)
