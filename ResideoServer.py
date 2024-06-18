"""
Municipalite des îles-de-la-madeleine
Iohann Paquette
2024-06-18
"""

"""""""""
Bibliothèques
"""""""""
from pyhtcc import PyHTCC
"""""""""
"""""""""

def afficher_option(user=PyHTCC):
    print(f'Connecte en tant que {user.username}...')
    print(f'-------------------------------------')
    
    choix = input('Choisir parmis les options suivante :\n'
              '1. Affichez tout les endroits\n'
              '2. Chercher par nom de sites\n'
              '3. Avoir les infos des différentes zones\n'
              '4. Se déconnecter\n'
              '-------------------------------------\n'
              '')
    while 0 > int(choix) > 4: #or not choix.isdigit():
        print('Mauvaise entrée, veuillez reessayer...')

        print(f'Choisir parmis les options suivante :\n')
        print('1.Affichez tout les endroit')
        print('2.Chercher par nom de sites')
        print('3.Avoir les infos des différentes zones')
        print('4.Se déconnecter et quitter')

        print(f'-------------------------------------')
        choix = int(input(''))

        match choix:
            case 1:
                get_all_zones(user)
            case 2:
                print(f'-------------------------------------')
                zone_name = input('Nom du building: ')
                user.get_zone_by_name()
            case 3:
                print(user.get_zones_info())
            case 4:
                deconnection(user)


    return int(choix)

def get_all_zones(user=PyHTCC):
    list = user.get_all_zones()

    for i in list:
        print(i)

def get_zone_by_name(user=PyHTCC,name=""):

    while(name == "" or name is None):
        name = input('Nom du building:')
        
    info = user.get_zone_by_name(name)
    print(info)

def deconnection(user=PyHTCC):
    try:
        user.logout()
        exit(1)
    except Exception as e:
        print(e)
        return

if __name__ == "__main__":
    email = input('Votre courriel : ')
    mdp = input('Mot de passe : ')

    user = PyHTCC(email, mdp)

    print('authentification...')
    try:   
        user.authenticate()

        choix = afficher_option(user)

    
    except Exception as e:
        print(e)
        user.logout()
    
