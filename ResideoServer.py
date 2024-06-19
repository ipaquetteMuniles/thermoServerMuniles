"""
Municipalité des îles-de-la-Madeleine
Iohann Paquette
2024-06-18
"""

"""
Bibliothèques
"""
import os
from pyhtcc import PyHTCC
from datetime import timedelta, datetime
import time
import schedule
import threading

"""
Constantes
"""
FILENAME = f'{datetime.today().strftime("%m/%d/%Y")}'

"""
Fonctions
"""

def afficher_option(user):
    """
    Affiche toutes les options possibles à l'utilisateur, comme premier menu
    """
    print(f'Connecté en tant que {user.username}...')
    print('-------------------------------------')
    
    choix = input('Choisir parmi les options suivantes :\n'
                  '1. Afficher les données des endroits\n'
                  '2. Chercher par nom de sites\n'
                  '3. Changer les paramètres d\'une zone\n'
                  '4. Obtenir les données (FICHIERS)\n'
                  '5. Se déconnecter\n'
                  '-------------------------------------\n')

    while not choix.isdigit() or not 1 <= int(choix) <= 5:
        print('Mauvaise entrée, veuillez réessayer...')
        choix = input('Choisir parmi les options suivantes :\n'
                      '1. Afficher les données des endroits\n'
                      '2. Chercher par nom de sites\n'
                      '3. Changer les paramètres d\'une zone\n'
                      '4. Obtenir les données (FICHIERS)\n'
                      '5. Se déconnecter\n'
                      '-------------------------------------\n')

    choix = int(choix)

    if choix == 1:
        zone = get_all_zones(user)
        afficher_zone_info(zone)

    elif choix == 2:
        print('-------------------------------------')
        zone_name = input('Nom du thermostat : ')
        get_zone_by_name(user, zone_name)

    elif choix == 3:
        zone = get_all_zones(user)
        setting_new_parameter(zone)

    elif choix == 4:
        zone = get_all_zones(user)
        get_data(zone)

    elif choix == 5:
        deconnection(user)

def get_data(zone):

    # Configurer le fichier CSV
    with open(f"{FILENAME}.csv", "w") as file:
        file.write("zone_id,zone_name,timestamp,temperature,displayUnits,indoor_humidity,outdoor_humidity,heat_setpoint,cool_setpoint,fan_status\n")

    print('-------------------------------------\n')

    print("1. MINUTES \n")
    print("2. HEURES \n")
    print("3. JOURS \n")
    
    option = int(input())
    every = int(input('Tous les (CHIFFRES) : '))

    while not 1 <= option <= 3:
        print('Réessayer')
        option = int(input())

    if option == 1:
        schedule.every(every).minutes.do(run_threaded, collect_data, zone)
    elif option == 2:
        schedule.every(every).hours.do(run_threaded, collect_data, zone)
    elif option == 3:
        schedule.every(every).days.do(run_threaded, collect_data, zone)
    
    os.system('cls' if os.name == 'nt' else 'clear')

    print("Écriture des données NE PAS FERMER LE PROGRAMME ...")

    while True:
        schedule.run_pending()
        time.sleep(1)

def run_threaded(job_func, *args):
    job_thread = threading.Thread(target=job_func, args=args)
    job_thread.start()

def collect_data(zone):
    zone_info, ui_data, fan_data = get_current_data(zone)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(f"{FILENAME}.csv", "a") as file:
        file.write(f"{zone.device_id},{zone_info['Name']},{timestamp},{ui_data['DispTemperature']},{ui_data['DisplayUnits']},{ui_data['IndoorHumidity']},{ui_data['OutdoorHumidity']},{ui_data['HeatSetpoint']},{ui_data['CoolSetpoint']},{fan_data['fanIsRunning']}\n")
    print(f'Data collected at {timestamp}')

def setting_new_parameter(zone):
    print(f'Actuel donnée sur {zone.zone_info["Name"]} | {zone.device_id}')
    print('-------------------------------------\n')

    afficher_zone_info(zone)

    afficher_menu_setter()

    choisir_option_setter(zone)

def get_temperature():
    """Fonction pour obtenir la température de l'utilisateur"""
    return int(input("Entrez la température souhaitée: "))

def get_end_time():
    """Fonction pour obtenir la durée de fin de l'utilisateur pour les consignes temporaires"""
    print('-------------------------------------\n')
    print("Choisissez le type de fin:")
    print("1. Durée (heures)")
    print("2. Heure précise (HH:MM)")
    choice = input("Votre choix (1-2): ")

    if choice == '1':
        hours = int(input("Entrez le nombre d'heures: "))
        return timedelta(hours=hours)
    elif choice == '2':
        end_time_str = input("Entrez l'heure (HH:MM): ")
        return datetime.strptime(end_time_str, "%H:%M").time()
    else:
        print("Choix invalide, aucune durée de fin spécifiée.")
        return None

def choisir_option_setter(zone):
    choice = int(input())

    while not 1 <= choice <= 9:
        afficher_menu_setter()
        choice = int(input())

    if choice == 1:
        temp = get_temperature()
        zone.set_permanent_cool_setpoint(temp)
    elif choice == 2:
        temp = get_temperature()
        zone.set_permanent_heat_setpoint(temp)
    elif choice == 3:
        temp = get_temperature()
        end = get_end_time()
        zone.set_temp_cool_setpoint(temp, end)
    elif choice == 4:
        temp = get_temperature()
        end = get_end_time()
        zone.set_temp_heat_setpoint(temp, end)
    elif choice == 5:
        zone.turn_fan_auto()
        print('Fan AUTO')
    elif choice == 6:
        zone.turn_fan_circulate()
        print("Fan est allumé pour circuler de l'air")
    elif choice == 7:
        zone.turn_fan_on()
        print('Fan ON')
    elif choice == 8:
        zone.turn_system_off()
        print('Fan OFF')
    elif choice == 9:
        return
    
    time.sleep(3)
    print('Nouveau paramètres : \n')
    afficher_zone_info(zone)

def afficher_menu_setter():
    print("\nMenu de Contrôle du Thermostat")
    print("1. Définir un point de consigne de refroidissement permanent")
    print("2. Définir un point de consigne de chauffage permanent")
    print("3. Définir un point de consigne de refroidissement temporaire")
    print("4. Définir un point de consigne de chauffage temporaire")
    print("5. Régler le ventilateur sur automatique (AUTO-(HEAT-OFF))")
    print("6. Régler le ventilateur sur circulation")
    print("7. Allumer le ventilateur (ON)")
    print("8. Éteindre le système (OFF)")
    print("9. Revenir au menu principal")
    print("\nVeuillez choisir une option (1-9): ", end="")

def get_current_data(zone):
    zone.refresh_zone_info()
    
    zone_info = zone.zone_info
    latest_data = zone_info['latestData']
    ui_data = latest_data['uiData']
    fan_data = latest_data['fanData']

    return zone_info, ui_data, fan_data


def afficher_zone_info(zone):
    """Fonction pour afficher les informations de chaque zone de manière lisible"""

    zone_info, ui_data, fan_data = get_current_data(zone)
   
    print(f"Zone ID: {zone.device_id}")
    print(f"Zone Name: {zone_info['Name']}")
    print(f"Current Temperature: {ui_data['DispTemperature']} {ui_data['DisplayUnits']}")
    print(f"Heat Setpoint: {ui_data['HeatSetpoint']} {ui_data['DisplayUnits']}")
    print(f"Cool Setpoint: {ui_data['CoolSetpoint']} {ui_data['DisplayUnits']}")
    print(f"System Switch Position: {ui_data['SystemSwitchPosition']}")
    print(f"Fan Mode: {fan_data['fanMode']}")
    print(f"Fan is Running: {fan_data['fanIsRunning']}")
    print(f"Indoor Humidity: {ui_data['IndoorHumidity']}")
    print(f"Outdoor Temperature: {ui_data['OutdoorTemperature']}")
    print(f"Outdoor Humidity: {ui_data['OutdoorHumidity']}")
    print(f"Alerts: {zone_info['Alerts']}")
    print("----------")
        
def get_all_zones(user):
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

def get_zone_by_name(user, name):
    while not name:
        name = input('Nom de la zone : ')
    try:
        zone = user.get_zone_by_name(name)
        afficher_zone_info(zone)
    except NameError as e:
        print(e)

def deconnection(user):
    try:
        print('Déconnexion...')
        user.logout()
        exit(1)
    except Exception as e:
        print(e)

if __name__ == "__main__":
    try:   
        email = input('Votre courriel : ')
        mdp = input('Mot de passe : ')
        
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print('Authentification...')

        # Authentification
        user = PyHTCC(email, mdp)
        
        choix = afficher_option(user)

        while choix != 5:
            choix = afficher_option(user)
    
    except Exception as e:
        print(e)
        exit(0)
