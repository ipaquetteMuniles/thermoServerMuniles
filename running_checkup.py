import requests
if __name__ == "__main__":
    url = 'https://iohann.pythonanywhere.com/'
    status_code = requests.get(url + 'get_status').status_code

    #205 = is running
    #206 = is NOT running
    if status_code == 205:
        print('already running :)')
    elif status_code == 206:
        print('Script not runnning,starting code...')
        requests.post(url + 'start')