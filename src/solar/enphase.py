# This file is part of Helios.
#
# Helios is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License version 3 as published by the Free Software Foundation.
# Helios is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with Helios.
# If not, see <https://www.gnu.org/licenses/>.

import os
import sys
import time
import requests
import urllib
import base64
import json
import logging
import pprint

from datetime import datetime
from dateutil import tz as timezone

l = logging.getLogger('helios')

class EnphaseInterface():
    def __init__(self, system_id, api_key, client_id, client_secret, auth_code, token_file):
        self.__system_id = system_id
        self.__api_key = api_key
        self.__client_id = client_id
        self.__client_secret = client_secret
        self.__auth_code = auth_code
        self.__token_file = token_file

        self.__api_url = 'https://api.enphaseenergy.com/api/v4'
        self.__redirect_url = 'https://api.enphaseenergy.com/oauth/redirect_uri'
        self.__auth_url = 'https://api.enphaseenergy.com/oauth/authorize'
        self.__refresh_url = 'https://api.enphaseenergy.com/oauth/token'

        self.__auth_tokens = None
        self.__access_headers = None
        self.__last_refresh = None

        auth_basic = base64.b64encode(f"{self.__client_id}:{self.__client_secret}".encode('ascii')).decode('ascii')
        self.__refresh_token_headers = { 'Authorization' : f'Basic {auth_basic}' }

        self.__fetch_tokens_data = { 'grant_type'   : 'authorization_code',
                                     'redirect_uri' : self.__redirect_url,
                                     'code'         : self.__auth_code }

    def print_auth_url(self):
        print("")
        print("Use this url to authorize access to your Enphase system")
        print("and retrieve an authorization code:")
        print("")
        print(f"{self.__auth_url}?response_type=code&client_id={self.__client_id}&redirect_uri={self.__redirect_url}")
        print("")

    def refresh_tokens(self):
        if self.__last_refresh:
            if (time.time() - self.__last_refresh) < 14400:
                return

        self.__auth_tokens = {}
        if os.path.exists(self.__token_file):
            l.debug(f"Found existing tokens in '{self.__token_file}', refreshing ...")
            with open(self.__token_file, 'r') as token_store:
                self.__auth_tokens = json.load(token_store)

            refresh_data = { 'grant_type'    : 'refresh_token',
                             'refresh_token' : self.__auth_tokens['refresh_token'] }

            for i in range(0,11):
                r = requests.post(self.__refresh_url, data=refresh_data, headers=self.__refresh_token_headers)
                if r.status_code == 200:
                    break
                time.sleep(3)

            if r.status_code == 200:
                self.__auth_tokens = r.json()
                with open(self.__token_file, 'w') as token_store:
                    json.dump(self.__auth_tokens, token_store)
            else:
                l.error(f"Failed to refresh Enphase auth tokens.  Exiting. {r}")
                exit(1)
        else:
            l.info(f"No tokens found, fetching ...")
            r = requests.post(self.__refresh_url, data=self.__fetch_tokens_data,
                headers=self.__refresh_token_headers)
            if r.status_code == 200:
                self.__auth_tokens = r.json()
                with open(self.__token_file, 'w') as token_store:
                    json.dump(self.__auth_tokens, token_store)
            else:
                l.error(f"Failed to get Enphase autho tokens.  Exiting. {r}")
                exit(1)

        self.__access_headers = { 'Authorization' : f"Bearer {self.__auth_tokens['access_token']}" }

        self.__last_refresh = time.time()

    def __get_energy_data(self, base_url, params, method):

        url = f"{base_url}/{method}{params}"
        api_path = urllib.parse.urlparse(url).path

        r = None
        for i in range(0,31):
            r = requests.get(url, headers=self.__access_headers)
            if r.status_code == 200:
                break
            elif r.status_code == 422:
                l.warn(f"Enphase API GET {api_path} => {r}")
                l.warn("Request understood, but could not be processed sleep for 5 minutes.")
                time.sleep(300)
            else:
                l.warn(f"Enphase API GET {api_path} => {r}")
                time.sleep(10)

        if r.status_code == 200:
            l.debug(f"Enphase API GET {api_path} => {r}")
        else:
            l.error(f"Enphase API GET {api_path} => {r}")

        return r.json()

    def __get_meter_data(self, method, last_n_seconds):
        granularity = 'week'
        start_at = time.time() - last_n_seconds

        base_url = f"{self.__api_url}/systems/{self.__system_id}/telemetry"
        params = f"?granularity={granularity}&start_at={start_at}&key={self.__api_key}"

        return self.__get_energy_data(base_url, params, method)

    def get_generation_range(self, tz, min_power=1220):
        tz = timezone.gettz(tz)
        energy_data = self.get_pro_meters(432000)

        time_one = None
        time_two = None

        gen = []

        for item in energy_data:
            dt = datetime.fromtimestamp(int(item['end_time']), tz=tz)
            gen.append([ dt.hour, item['pwr_produced']] )

        sorter = lambda x: (x[1], x[0])
        sorted_gen = sorted(gen, key=sorter)
        for l in gen:
            if l[0] >= 12:
                if not time_two:
                    if l[1] < 1200 and l[1] > 900:
                        time_two = l[0]
            else:
                if not time_one:
                    if l[1] >= 1200 and l[1] < 1400:
                        time_one = l[0]

        gen_range = []
        for i in range(time_one, time_two+1):
            gen_range.append(i)

        return gen_range

    def get_battery_charge(self):
        bat = self.__get_meter_data('battery', 3600)

        battery_data = { 'level' : None, 'intervals' : [] }

        max_len = len(bat['intervals'])
        for i in range(0, max_len):
            interval = {}
            interval['level'] = bat['intervals'][i]['soc']['percent']
            interval['pwr_charged'] = bat['intervals'][i]['charge']['enwh'] * 4
            battery_data['intervals'].append(interval)

        battery_data['level'] = int(bat['last_reported_aggregate_soc'][:-1])

        return battery_data

    def get_pro_meters(self, last_n_seconds=3600):
        energy_data = []

        pro = self.__get_meter_data('production_meter', last_n_seconds)

        max_len = len(pro['intervals'])
        for i in range(0, max_len):
            interval = { 'end_time'      : pro['intervals'][i]['end_at'],
                         'dt'            : time.ctime(pro['intervals'][i]['end_at']),
                         'eng_produced'  : pro['intervals'][i]['wh_del'],
                         'pwr_produced'  : pro['intervals'][i]['wh_del'] * 4 }

            energy_data.append(interval)

        return energy_data

    def get_meters(self, last_n_seconds=3600):
        energy_data = []

        pro = self.__get_meter_data('production_meter', last_n_seconds)
        con = self.__get_meter_data('consumption_meter', last_n_seconds)

        max_len = len(pro['intervals'])
        for i in range(0, max_len):
            exported = pro['intervals'][i]['wh_del'] - con['intervals'][i]['enwh']

            interval = { 'end_time'      : pro['intervals'][i]['end_at'],
                         'dt'            : time.ctime(pro['intervals'][i]['end_at']),
                         'eng_produced'  : pro['intervals'][i]['wh_del'],
                         'eng_consumed'  : con['intervals'][i]['enwh'],
                         'eng_exported'  : exported,
                         'pwr_produced'  : pro['intervals'][i]['wh_del'] * 4,
                         'pwr_consumed'  : con['intervals'][i]['enwh'] * 4,
                         'pwr_exported'  : exported * 4 }

            energy_data.append(interval)

        return energy_data
