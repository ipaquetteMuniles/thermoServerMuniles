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
from firebase_admin import credentials,db
import json
import pytz

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

        data = {
            "device_id": device_id,
            "zone_name": zone_name,
            "timestamp": timestamp,
            "display_temperature": ui_data['DispTemperature'],
            "outdoor_temperature": ui_data['OutdoorTemperature'],
            "display_units": ui_data['DisplayUnits'],
            "indoor_humidity": ui_data['IndoorHumidity'],
            "outdoor_humidity": ui_data['OutdoorHumidity'],
            "heat_setpoint": ui_data['HeatSetpoint'],
            "cool_setpoint": ui_data['CoolSetpoint'],
            "fan_is_running": fan_data['fanIsRunning']
        }

        self.write_in_db(zone_name,device_id,data)
        print(f'Data collected at {timestamp}')

    def write_in_db(self,zone_name,device_id,data):
        try:
            ref = db.reference(f'/{device_id}/{zone_name}/{datetime.today().strftime("%m-%d-%Y")}-THERMOSTAT_DATA')
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
