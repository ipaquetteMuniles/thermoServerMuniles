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

def afficher_option(user):
    print(f'Connecté en tant que {user.username}...')
    print('-------------------------------------')
    
    choix = input('Choisir parmi les options suivantes :\n'
                  '1. Afficher tous les endroits\n'
                  '2. Chercher par nom de sites\n'
                  '3. Avoir les infos des différentes zones\n'
                  '4. Se déconnecter\n'
                  '-------------------------------------\n')

    while not choix.isdigit() or not 1 <= int(choix) <= 4:
        print('Mauvaise entrée, veuillez réessayer...')
        choix = input('Choisir parmi les options suivantes :\n'
                      '1. Afficher tous les endroits\n'
                      '2. Chercher par nom de sites\n'
                      '3. Avoir les infos des différentes zones\n'
                      '4. Se déconnecter\n'
                      '-------------------------------------\n')

    choix = int(choix)

    if choix == 1:
        get_all_zones(user)
    elif choix == 2:
        print('-------------------------------------')
        zone_name = input('Nom du bâtiment : ')
        get_zone_by_name(user, zone_name)
    elif choix == 3:
        print(user.get_zones_info())
    elif choix == 4:
        deconnection(user)

# Fonction pour afficher les informations de chaque zone de manière lisible
def afficher_zone_info(zone):
    zone_info = zone.zone_info
    latest_data = zone_info['latestData']
    ui_data = latest_data['uiData']
    fan_data = latest_data['fanData']
    
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
        
def get_all_zones(user=PyHTCC):
    os.system('cls' if os.name == 'nt' else 'clear')
   
    print('En recherche ...')
    zones = user.get_all_zones()

    print('Différentes localisations:')
    print('-------------------------------------')

    i = 1

    for zone in zones:
        print(f"{i}\tZone ID: {zone.device_id} | Zone Name: { zone.zone_info['Name']}\n")
        i +=1

    choix = input('Affichez les infos de la zone # :')

    while(choix < 0 or choix > len(zones)):
        print('Reessayer...')
        choix = input('Affichez les infos de la zone # :')

    choix = int(choix)

    afficher_zone_info(zones[choix-1])


def get_zone_by_name(user, name):
    try:
        while not name:
            name = input('Nom du bâtiment : ')
        info = user.get_zone_by_name(name)
    except NameError as e:
        print(e)

def deconnection(user):
    try:
        print('Deconnexion...')
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

        while choix != 4:
            choix = afficher_option(user)
    
    except Exception as e:
        print(e)
        exit(0)