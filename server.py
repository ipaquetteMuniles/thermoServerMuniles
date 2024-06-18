import urllib.parse
import urllib3
import json
import urllib
import datetime
import re
import time
import base64
import sys
import yaml
from enum import Enum

class TotalComfortAction(Enum):
    STATUS = 1
    JSON = 2
    CANCEL = 3
    COOL = 4
    HEAT = 5
    MODE = 6
    FAN = 7

AUTH = "https://mytotalconnectcomfort.com/portal"

cookiere = re.compile(r'\s*([^=]+)\s*=\s*([^;]*)\s*')

def client_cookies(cookiestr, container=None):
    if container is None:
        container = {}
    toks = re.split(';|,', cookiestr)
    for t in toks:
        m = cookiere.search(t)
        if m:
            k, v = m.group(1), m.group(2)
            if k.lower() not in ['path', 'httponly']:
                container[k] = v
    return container

def export_cookiejar(jar):
    return '; '.join([f'{k}={v}' for k, v in jar.items()])

def execute(action: TotalComfortAction, value=0, hold_time=1):
    with open('./credentials.yaml') as f:
      credentials = yaml.safe_load(f)
    
    print(f"trying to login {credentials['username']} ...")
    cookiejar = None

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "sdch",
        "Host": "mytotalconnectcomfort.com",
        "DNT": "1",
        "Origin": "https://mytotalconnectcomfort.com/portal",
        "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/28.0.1500.95 Safari/537.36"
    }

    conn = urllib3.PoolManager()
    r0 = conn.request("GET", AUTH, headers=headers)
    
    for k, v in r0.headers.items():
        if k.lower() == "set-cookie":
            cookiejar = client_cookies(v, cookiejar)
    
    newcookie = export_cookiejar(cookiejar)
    #location = r1.getheader("Location")

    params = urllib.parse.urlencode({
        "timeOffset": "240",
        "UserName": credentials['username'],
        "Password": credentials['password'],
        "RememberMe": "false"
    })
    
    headers["Cookie"] = newcookie
    r1 = conn.request("POST", AUTH, body=params, headers=headers, redirect=False)
    
    for k, v in r1.headers.items():
        if k.lower() == "set-cookie":
            cookiejar = client_cookies(v, cookiejar)
    cookie = export_cookiejar(cookiejar)

    if r1.status != 302:
        print(f"Error: Never got redirect on initial login, status={r1.status} {r1.reason}")
        return

    code = str(credentials['device_id'])
    print(f'entering code {code} .. \n')

    t = datetime.datetime.now()
    utc_seconds = int(time.mktime(t.timetuple()) * 1000)

    # location = AUTH + "/Device/CheckDataSession/" + code + "?_=" + str(utc_seconds)
    location="/portal/Device/CheckDataSession/"+code+"?_="+str(utc_seconds)

    headers = {
        "Accept": "*/*",
        "DNT": "1",
        "Accept-Encoding": "plain",
        "Cache-Control": "max-age=0",
        "Accept-Language": "en-US,en,q=0.8",
        "Connection": "keep-alive",
        "Host": "mytotalconnectcomfort.com",
        "Referer": "https://mytotalconnectcomfort.com/portal/",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/28.0.1500.95 Safari/537.36",
        "Cookie": cookie
    }

    r3 = conn.request("GET", location, headers=headers)
    print(r3.status)
    if r3.status != 200:
        print("Error: Didn't get 200 status on R3, status={0} {1}".format(r3.status, r3.reason))
        return

    if action == TotalComfortAction.STATUS:
        rawdata = r3.data
        j = json.loads(rawdata.decode('utf-8'))
        print("Indoor Temperature:", j['latestData']['uiData']["DispTemperature"])
        print("Indoor Humidity:", j['latestData']['uiData']["IndoorHumidity"])
        print("Cool Setpoint:", j['latestData']['uiData']["CoolSetpoint"])
        print("Heat Setpoint:", j['latestData']['uiData']["HeatSetpoint"])
        print("Hold Until:", j['latestData']['uiData']["TemporaryHoldUntilTime"])
        print("Status Cool:", j['latestData']['uiData']["StatusCool"])
        print("Status Heat:", j['latestData']['uiData']["StatusHeat"])
        print("Status Fan:", j['latestData']['fanData']["fanMode"])
        return

    if action == TotalComfortAction.JSON:
        rawdata = r3.data
        j = json.loads(rawdata.decode('utf-8'))
        print(json.dumps(j, indent=2))
        return j

    headers = {
        "Accept": 'application/json; q=0.01',
        "DNT": "1",
        "Accept-Encoding": "gzip,deflate,sdch",
        'Content-Type': 'application/json; charset=UTF-8',
        "Cache-Control": "max-age=0",
        "Accept-Language": "en-US,en,q=0.8",
        "Connection": "keep-alive",
        "Host": "mytotalconnectcomfort.com",
        "Referer": "https://mytotalconnectcomfort.com/portal/",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/28.0.1500.95 Safari/537.36",
        "Cookie": cookie
    }

    payload = {
        "CoolNextPeriod": None,
        "CoolSetpoint": None,
        "DeviceID": credentials['device_id'],
        "FanMode": None,
        "HeatNextPeriod": None,
        "HeatSetpoint": None,
        "StatusCool": None,
        "StatusHeat": None,
        "SystemSwitch": None
    }

    t = datetime.datetime.now()
    stop_time = ((t.hour + hold_time) % 24) * 60 + t.minute
    stop_time = stop_time // 15

    if action == TotalComfortAction.COOL:
        payload["CoolSetpoint"] = value
        payload["StatusCool"] = 1
        payload["StatusHeat"] = 1
        payload["CoolNextPeriod"] = stop_time

    if action == TotalComfortAction.HEAT:
        payload["HeatSetpoint"] = value
        payload["StatusCool"] = 1
        payload["StatusHeat"] = 1
        payload["HeatNextPeriod"] = stop_time

    if action == TotalComfortAction.MODE:
        payload["SystemSwitch"] = value

    if action == TotalComfortAction.CANCEL:
        payload["StatusCool"] = 0
        payload["StatusHeat"] = 0

    if action == TotalComfortAction.FAN:
        payload["FanMode"] = value

    location = "/portal/Device/SubmitControlScreenChanges"
#    location = AUTH + "/Device/SubmitControlScreenChanges"

    rawj = json.dumps(payload)
    r4 = conn.request("POST", location, body=rawj, headers=headers)
    if r4.status != 200:
        print("Error: Didn't get 200 status on R4, status={0} {1}".format(r4.status, r4.reason))
    else:
        print("Success in configuring thermostat!")

def printUsage():
    print("")
    print("Cooling: -c temperature -t hold_time")
    print("Heating: -h temperature -t hold_time")
    print("Status: -s")
    print("Full Status JSON format: -j")
    print("Cancel: -x")
    print("Fan: -f [0=auto|1=on]")
    print("Mode: -m [0=EmHeat|1=Heat|2=Off|3=Cool]")
    print("")
    print("Example: Set temperature to cool to 80f for 1 hour: \n\ttotalcomfort.py -c 80 -t 1")
    print("")
    print("If no -t hold_time is provided, it will default to one hour from command time.")
    print("")

def main():

    if len(sys.argv) < 2 or sys.argv[1] == "-s":
        execute(TotalComfortAction.STATUS)
        sys.exit()

    if sys.argv[1] == "-j":
        execute(TotalComfortAction.JSON)
        sys.exit()

    if sys.argv[1] == "-x":
        execute(TotalComfortAction.CANCEL)
        sys.exit()

    if sys.argv[1] == "-c" and len(sys.argv) > 2:
        value = int(sys.argv[2])
        hold_time = 1
        if len(sys.argv) > 3 and sys.argv[3] == "-t":
            hold_time = int(sys.argv[4])
        execute(TotalComfortAction.COOL, value, hold_time)
        sys.exit()

    if sys.argv[1] == "-h" and len(sys.argv) > 2:
        value = int(sys.argv[2])
        hold_time = 1
        if len(sys.argv) > 3 and sys.argv[3] == "-t":
            hold_time = int(sys.argv[4])
        execute(TotalComfortAction.HEAT, value, hold_time)
        sys.exit()

    if sys.argv[1] == "-f" and len(sys.argv) > 2:
      value = int(sys.argv[2])
      execute(TotalComfortAction.FAN, value)
      sys.exit()

    if sys.argv[1] == "-m" and len(sys.argv) > 2:
      value = int(sys.argv[2])
      execute(TotalComfortAction.MODE, value)
      sys.exit()

    if sys.argv[1] == "-help":
      printUsage()
      sys.exit()

    print("Unknown arguments:", sys.argv[1:])
    printUsage()
    sys.exit()

if __name__ == "__main__":
    main()
