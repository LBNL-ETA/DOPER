# Advanced Fenestration Controller (AFC) Copyright (c) 2023, The
# Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

""""Advanced Fenestration Controller
Watttime module.
"""

# pylint: disable=redefined-outer-name, invalid-name, too-many-arguments, duplicate-code

import os
import json
import requests
import pandas as pd
from requests.auth import HTTPBasicAuth

TIMEOUT = 5 # seconds

urls = {}
urls['register_url'] = 'https://api2.watttime.org/v2/register'
urls['login_url'] = 'https://api2.watttime.org/v2/login'
urls['password_url'] = 'https://api2.watttime.org/v2/password'
urls['region_url'] = 'https://api2.watttime.org/v2/ba-from-loc'
urls['list_url'] = 'https://api2.watttime.org/v2/ba-access'
urls['index_url'] = 'https://api2.watttime.org/index'
urls['data_url'] = 'https://api2.watttime.org/v2/data'
urls['historical_url'] = 'https://api2.watttime.org/v2/historical'
urls['forecast_url'] = 'https://api2.watttime.org/v2/forecast'

def check_response(response):
    """check if request returned successfully"""
    if response.status_code == 200:
        return response
    print(f'Error: {response.status_code}')
    with open('response_error.html', 'w', encoding='utf8') as f:
        f.write(response.text)
    return None

class Watttime:
    """client for Watttime emission forecasting"""
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
        params = {'username': self.username,
                  'password': self.password,
                  'email': self.email,
                  'org': self.org}
        response = requests.post(urls['register_url'], json=params, timeout=TIMEOUT)
        if check_response(response):
            print(response.text)
        else:
            raise ValueError('The registration was not successful. Check the response_error.html')

    def login(self):
        """login to Watttime"""
        response = requests.get(urls['login_url'],
                                auth=HTTPBasicAuth(self.username, self.password),
                                timeout=TIMEOUT)
        if check_response(response):
            self.token = response.json()['token']

    def get_regions(self, all_regions=False):
        """list all regions
        
        Inputs:
        all_regions (bool): Flag to query all available regions.
        """
        if not self.token:
            self.login()
        headers = {'Authorization': f'Bearer {self.token}'}
        params = {'all': str(all_regions)}
        response = requests.get(urls['list_url'], headers=headers, params=params, timeout=TIMEOUT)
        if check_response(response):
            return json.loads(response.text)
        return None

    def get_emission_historic(self, ba='CAISO_NORTH',
                              cur_dir=os.path.dirname(os.path.realpath('__file__'))):
        """get historic emissions
        
        Inputs:
        ba (str): Balancing authority.
        cur_dir (str): Directory to store downloaded zip file.
        """
        if not self.token:
            self.login()
        headers = {'Authorization': f'Bearer {self.token}'}
        params = {'ba': str(ba)}
        response = requests.get(urls['historical_url'], headers=headers,
                                params=params, timeout=TIMEOUT)
        if check_response(response):
            file_path = os.path.join(cur_dir, f'{ba}_historical.zip')
            with open(file_path, 'wb') as f:
                f.write(response.content)

    def get_emission_forecast(self, ba='CAISO_NORTH', extended_forecast=False):
        """get emission forecast
        
        Inputs:
        ba (str): Balancing authority.
        extended_forecast (bool): Provides an extended 72 hour instead of 24 hour forecast.
        """
        if not self.token:
            self.login()
        headers = {'Authorization': f'Bearer {self.token}'}
        params = {'ba': str(ba),
                  'extended_forecast': str(extended_forecast)}
        response = requests.get(urls['forecast_url'], headers=headers,
                                params=params, timeout=TIMEOUT)
        if check_response(response):
            return json.loads(response.text)
        return None

if __name__ == "__main__":
    # setup credentials
    creds = {'registered': True}
    if os.path.exists('creds_watttime.json'):
        with open('creds_watttime.json', encoding='utf8') as f:
            creds.update(json.loads(f.read()))

    # initialize client
    client = Watttime(**creds)

    # get regions
    data = client.get_regions(all_regions=False)
    print(data)

    # get historical
    client.get_emission_historic()

    # get forecast
    data = client.get_emission_forecast()
    if data:
        print(pd.DataFrame(data['forecast']))
