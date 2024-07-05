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
# desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
# FILENAME = os.path.join(desktop_path,datetime.today().strftime("%m_%d_%Y"))

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
    def __init__(self, user):
        """
        Constructeur
        user : pyhtcc connection
        """

        self.user = user
        self.zones = user.get_all_zones()
        self.running = True  # Flag to control the main loop

    def run_schedule(self):
        try:
            while self.running:
                schedule.run_pending()
                time.sleep(1)
        except Exception as e:
            input()
            print(e)
            print('Déconnexion...')
            self.user.logout()
            exit(1)

    def get_temperature(self):
        # Constants
        LONGITUDE = -61.750022
        LATITUDE = 47.445642
        TIMEZONE = 'America/Goose_Bay'
        
        # API URL and parameters
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "minutely_15": "temperature_2m,relative_humidity_2m",
            "timezone": TIMEZONE
        }

        try:
            # Fetch the weather data
            response = requests.get(url, params=params)
            response.raise_for_status()
            response = response.json()
            
            # Process minutely data
            minutely_data = response.get('minutely_15', {})
            
            if not minutely_data:
                raise ValueError("No minutely data found in API response.")
            
            minutely_times = pd.to_datetime(minutely_data.get('time', []), utc=True).tz_convert(TIMEZONE)
            minutely_temperature_2m = minutely_data.get('temperature_2m', [])
            minutely_humidity_2m = minutely_data.get('relative_humidity_2m', [])
            
            if not minutely_times.empty and len(minutely_temperature_2m) > 0 and len(minutely_humidity_2m) > 0:
                # Get the current time and subtract 15 minutes
                current_time = datetime.now(pytz.timezone(TIMEZONE))
                target_time = current_time - timedelta(minutes=15)
                
                # Initialize variables for closest time and data
                closest_time = None
                closest_temperature = None
                closest_humidity = None
                min_difference = timedelta.max
                
                # Find the closest timestamp to the target time
                for i, time in enumerate(minutely_times):
                    time_difference = abs(time - target_time)
                    if time_difference < min_difference:
                        min_difference = time_difference
                        closest_time = time
                        closest_temperature = minutely_temperature_2m[i]
                        closest_humidity = minutely_humidity_2m[i]
                
                # Print the result
                if closest_time is not None and closest_temperature is not None and closest_humidity is not None:
                    print(f"Closest time: {closest_time}, Temperature: {closest_temperature}, Humidity: {closest_humidity} % ")
                    return closest_temperature, closest_humidity
                else:
                    print("No valid minutely data found.")
            else:
                print("No valid minutely data found.")
        
        except requests.RequestException as e:
            print(f"Error fetching data from Open-Meteo API: {e}")
        except ValueError as ve:
            print(f"Error processing data: {ve}")
        except Exception as ex:
            print(f"An unexpected error occurred: {ex}")

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
            try:
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
                print(e)



        except Exception as e:
            print(e)
            self.user.logout()
            exit(1)

    def collect_data(self, zone):
        zone_info, ui_data, fan_data = self.get_current_data(zone)

        utcmoment_naive = datetime.now(pytz.utc)
        utcmoment = utcmoment_naive.replace(tzinfo=pytz.utc)

        #changment pour les îles de la madeleine
        timestamp = utcmoment.astimezone(pytz.timezone('America/Goose_Bay')).strftime("%Y-%m-%d %H:%M:%S")

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

        self.write_in_db(zone_name,device_id,data)
        print(f'Data collected at {timestamp}')

    def write_in_db(self,zone_name,device_id,data):
        try:
            ref = db.reference(f'/{device_id}/{zone_name}/{datetime.now(pytz.utc).today().strftime("%m-%d-%Y")}-THERMOSTAT_DATA')
            ref.push(data)
        except:
            print("Erreur dans l'écriture de la base de données..")
            self.user.logout()

    def get_all_zones(self, user):
        os.system('cls' if os.name == 'nt' else 'clear')

        print('En recherche ...')
        zones = user.get_all_zones()

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
        email = input('Votre courriel : ')
        mdp = input('Mot de passe : ')

        os.system('cls' if os.name == 'nt' else 'clear')

        print('Authentification...')

        # Authentification
        user = PyHTCC(email, mdp)

        # Création du collecteur de données
        c = Collector(user)
        # Retour de la zone qu'on désire obtenir les données
        zone = c.get_all_zones(user)

        c.get_data(zone)

    except Exception as e:
        print(e)
        exit(0)
