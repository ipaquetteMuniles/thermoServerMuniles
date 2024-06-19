"""
Municipalité des îles-de-la-Madeleine
Iohann Paquette
2024-06-18
"""

"""
Bibliothèques
"""
import csv
import time
from datetime import datetime, timedelta
from pyhtcc import PyHTCC
import os
import schedule

"""
Constantes
"""
FILENAME = datetime.today().strftime("%m_%d_%Y")

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

    def run_schedule(self):
        try:
            while True:
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
    
    def get_data(self, zone):
        try:
            # Configurer le fichier CSV
            with open(f"{FILENAME}.csv", "w+") as file:
                file.write("zone_id,zone_name,timestamp,indoor_temperature,outdoor_temperature,displayUnits,indoor_humidity,outdoor_humidity,heat_setpoint,cool_setpoint,fan_status\n")

            print('-------------------------------------\n')
            print("1. MINUTES")
            print("2. HEURES")
            print("3. JOURS")
            print('-------------------------------------')

            option = int(input())
            every = int(input('Tous les (CHIFFRES) : '))

            while not 1 <= option <= 3:
                print('Réessayer')
                option = int(input())

            if option == 1:
                schedule.every(every).minutes.do(self.collect_data, zone)
            elif option == 2:
                schedule.every(every).hours.do(self.collect_data, zone)
            elif option == 3:
                schedule.every(every).days.do(self.collect_data, zone)
            
            print("Écriture des données NE PAS FERMER LE PROGRAMME ...")

            self.run_schedule()
        except Exception as e:
            print(e)
            self.user.logout()
            exit(1)

    def collect_data(self, zone):
        zone_info, ui_data, fan_data = self.get_current_data(zone)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        data = f"{zone.device_id},{zone_info['Name']},{timestamp},{ui_data['DispTemperature']},{ui_data['OutdoorTemperature']},{ui_data['DisplayUnits']},{ui_data['IndoorHumidity']},{ui_data['OutdoorHumidity']},{ui_data['HeatSetpoint']},{ui_data['CoolSetpoint']},{fan_data['fanIsRunning']}\n"

        with open(f"{FILENAME}.csv", "a") as file:
            file.write(data)
        print(f'Data collected at {timestamp}, {data}')

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
    email = input('Votre courriel : ')
    mdp = input('Mot de passe : ')
        
    os.system('cls' if os.name == 'nt' else 'clear')
        
    print('Authentification...')

    # Authentification
    user = PyHTCC(email, mdp)
        
    # Création du collecteur de données
    c = Collector(user)

    try:   
        
        # Retour de la zone qu'on désire obtenir les données
        zone = c.get_all_zones(user)

        c.get_data(zone)
    
    except Exception as e:
        print(e)
        c.user.logout()
        exit(0)
