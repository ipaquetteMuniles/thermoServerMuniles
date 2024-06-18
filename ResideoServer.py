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
        
def get_all_zones(user):
    print('Différentes localisations:')
    print('-------------------------------------')
    

def get_zone_by_name(user, name):
    try:
        while not name:
            name = input('Nom du bâtiment : ')
        info = user.get_zone_by_name(name)
    except NameError as e:
        print(e)



def deconnection(user):
    try:
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
