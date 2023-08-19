# Advanced Fenestration Controller (AFC) Copyright (c) 2023, The
# Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

""""Advanced Fenestration Controller
Midas module.

Examples taken from:
https://github.com/morganmshep/MIDAS-Python-Repository/tree/main
"""

# pylint: disable=redefined-outer-name, invalid-name, too-many-arguments, duplicate-code

import os
import json
import base64
import requests
import pandas as pd

TIMEOUT = 5 # seconds

urls = {}
urls['register_url'] = 'https://midasapi.energy.ca.gov/api/registration'
urls['login_url'] = 'https://midasapi.energy.ca.gov/api/token'
urls['rin_url'] = 'https://midasapi.energy.ca.gov/api/valuedata?signaltype='
urls['value_url'] = 'https://midasapi.energy.ca.gov/api/valuedata?id='

def check_response(response):
    """check if request returned successfully"""
    if response.status_code == 200:
        return response
    print(f'Error: {response.status_code}')
    with open('response_error.html', 'w', encoding='utf8') as f:
        f.write(response.text)
    return None

def str_to_64(s):
    """convert str to 64bit"""
    encodedBytes = base64.b64encode(s.encode("utf-8"))
    return str(encodedBytes, "utf-8")

class Midas:
    """client for Midas emission forecasting"""
    def __init__(self, registered=True, username='freddo', password='the_frog!',
                 email='freddo@frog.org', org='freds world'):

        self.registered = registered
        self.username = username
        self.password = password
        self.email = email
        self.org = org

        self.token = None

        # Do registration if not already registered
        if not self.registered:
            self.register()

    def register(self):
        """register new user"""
        registration_info = {"organization": str_to_64(self.org),
                             "username": str_to_64(self.username),
                             "password": str_to_64(self.password),
                             "emailaddress": str_to_64(self.email),
                             "fullname": str_to_64(self.username)}
        headers = {"Content-Type": "application/json"}
        response = requests.post(urls['register_url'],
                                 data=json.dumps(registration_info),
                                 headers=headers,
                                 timeout=TIMEOUT)
        if check_response(response):
            print(response.text)
        else:
            raise ValueError('The registration was not successful. Check the response_error.html')

    def login(self):
        """login to Midas"""
        credentials = f'{self.username}:{self.password}'
        credentials_encodedBytes = base64.b64encode(credentials.encode("utf-8"))
        headers = {b'Authorization': b'BASIC ' + credentials_encodedBytes}
        response = requests.get(urls['login_url'],
                                headers=headers,
                                timeout=TIMEOUT)
        if check_response(response):
            self.token = response.headers['Token']

    def get_rins(self, signaltype=0):
        """list all Rate Identification Numbers (RINs)
        
        Inputs:
        signaltype (int): 0-all, 1-Tariffs, 2-GHG, 3-Flex Alerts.
        """
        if not self.token:
            self.login()
        headers = {'accept': 'application/json', 'Authorization': "Bearer " + self.token}
        url = f'{urls["rin_url"]}{str(signaltype)}'
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        if check_response(response):
            return json.loads(response.text)
        return None

    def get_values(self, rateID='USCA-FLEX-FXFC-0000', queryType='alldata'):
        """get Rate Identification Number (RIN) values
        
        Inputs:
        rateID (str): The rate ID, see ret_rins function.
        queryType (str): alldata or realtime.
        """
        headers = {'accept': 'application/json', 'Authorization': "Bearer " + self.token}
        url = f'{urls["value_url"]}{rateID}&querytype={queryType}'
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        if check_response(response):
            return json.loads(response.text)
        return None

if __name__ == "__main__":
    # setup credentials
    creds = {'registered': True}
    if os.path.exists('creds_midas.json'):
        with open('creds_midas.json', encoding='utf8') as f:
            creds.update(json.loads(f.read()))

    # initialize client
    client = Midas(**creds)

    # get regions
    data = client.get_rins(signaltype=0)
    data = pd.DataFrame(data)
    data.to_csv('all_rins.csv')
    print(data)

    # get values
    data = client.get_values(rateID='USCA-FLEX-FXFC-0000') # flexalert forecast
    print(pd.DataFrame(data['ValueInformation']))

    data = client.get_values(rateID='USCA-SGIP-SGFC-PGE') # pg&e emission forecast
    print(pd.DataFrame(data['ValueInformation']))
