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

import os.path
import time
import requests
import urllib
import json
import logging

l = logging.getLogger('helios')

class TeslaBaseClass():
    def __init__(self, geoapify, token_file):
        self._geoapify = geoapify
        self._token_file = token_file

        self._client_id = 'ownerapi'
        self._scope = 'openid email offline_access'
        self._api_url = 'https://owner-api.teslamotors.com/api/1'
        self._refresh_url = 'https://auth.tesla.com/oauth2/v3/token'

        self.__last_refresh = None
        self._access_headers = None

        self.refresh_tokens()

    def _post(self, url, body, retries=10, sleep=1.1):
        api_path = urllib.parse.urlparse(url).path
        retries += 1

        r = None
        for i in range(0,retries):
            try:
                r = requests.post(url, data=json.dumps(body), headers=self._access_headers)
            except requests.exceptions.ConnectionError as err:
                l.error(f"Tesla API POST {api_path} => {err}")
                time.sleep(300)

            if r.status_code == 200:
                break
            elif r.status_code == 401:
                time.sleep(60)
                self.refresh_tokens(True)
            elif r.status_code == 503:
                time.sleep(3600)
            else:
                time.sleep(sleep)
            sleep = sleep * 1.1 ** i

        if r.status_code == 200:
            l.debug(f"Tesla API POST {api_path} => {r}")
        else:
            l.error(f"Tesla API POST {api_path} => {r}")

        return r

    def _get(self, url, params, retries=10, sleep=1.1):
        api_path = urllib.parse.urlparse(url).path
        retries += 1

        r = None
        for i in range(0, retries):
            r = requests.get(url, params, headers=self._access_headers)
            if r.status_code == 200:
                break
            elif r.status_code == 401:
                time.sleep(60)
                self.refresh_tokens(True)
            else:
                time.sleep(sleep)
            sleep = sleep * 1.1 ** i

        if r.status_code == 200:
            l.debug(f"Tesla API GET {api_path} => {r}")
        else:
            l.error(f"Tesla API GET {api_path} => {r}")

        return r

    def refresh_tokens(self, force=False):
        if self.__last_refresh and not force:
            if (time.time() - self.__last_refresh) < 7200:
                return

        auth_tokens = {}

        l.debug(f"Found existing tokens in '{self._token_file}', refreshing ...")
        with open(self._token_file, 'r') as token_store:
            auth_tokens = json.load(token_store)

        refresh_data = { 'grant_type'    : 'refresh_token',
                         'client_id'     : self._client_id,
                         'refresh_token' : auth_tokens['refresh_token'],
                         'scope'         : self._scope }

        r = requests.post(self._refresh_url, data=refresh_data)
        if r.status_code == 200:
            auth_tokens = r.json()
            with open(self._token_file, 'w') as token_store:
                json.dump(auth_tokens, token_store)
        else:
            l.error(f"Failed to refresh Tesla auth tokens => {r}.  Exiting.")
            exit(1)

        self._auth_tokens = auth_tokens

        self._access_headers = { 'Authorization' : f"Bearer {self._auth_tokens['access_token']}" }

        self.__last_refresh = time.time()

    def get_vehicles(self):
        url = f"{self._api_url}/vehicles"

        r = self._get(url, {})

        return r.json()['response']

class TeslaInterface(TeslaBaseClass):
    def __init__(self, vehicle_id, geoapify, token_file):
        TeslaBaseClass.__init__(self, geoapify, token_file)

        self._vehicle_id = vehicle_id

        self.__init_stats_file = f".{vehicle_id}_init_stats.json"
        self.__latest_stats_file = f".{vehicle_id}_latest_stats.json"

        self.__init_charging_stats = None
        self.__latest_charging_stats = None

        self.__init_initial_charging_stats()
        self.__init_latest_charging_stats()

    def __init_initial_charging_stats(self):
        l.debug("Retrieving and storing initial charging statistics.")
        cs = self.get_charging_stats()

        with open(self.__init_stats_file, 'w') as init_stats:
            json.dump(cs, init_stats)

        self.__init_charging_stats = cs

    def __init_latest_charging_stats(self):
        if os.path.exists(self.__latest_stats_file):
            l.debug("Retrieving last charging statistics.")
            cs = {}
            with open(self.__latest_stats_file, 'r') as latest_stats:
                cs = json.load(latest_stats)

            self.__latest_charging_stats = cs

    def store_latest_stats(self):
        cs = self.get_charging_stats()

        with open(self.__latest_stats_file, 'w') as latest_stats:
            json.dump(cs, latest_stats)

        self.__latest_charging_stats = cs

    def reset_charge_configuration(self):
        self.set_charging_amps(self.__init_charging_stats['charge_current_request'])

    def wake(self):
        url = f"{self._api_url}/vehicles/{self._vehicle_id}/wake_up"

        for i in range(0,11):
            r = self._post(url, {}, 1, 0)
            if r.status_code == 200:
                r_json = r.json()['response']
                if r_json and r_json['state'] == 'online':
                    break
                time.sleep(5)

        r_json = r.json()['response']
        if r_json['state'] != 'online':
            l.warning(f"Failed to wake up Tesla {r_json['display_name']}.")

    def set_charging_amps(self, amps):
        self.wake()
        url = f"{self._api_url}/vehicles/{self._vehicle_id}/command/set_charging_amps"
        body = { 'charging_amps' : amps }

        l.info(f"Setting charging amps to {amps}.")
        self._post(url, body)
        self._post(url, body)

    def start_charging(self):
        self.wake()
        url = f"{self._api_url}/vehicles/{self._vehicle_id}/command/charge_start"

        l.info("Starting to charge.")
        self._post(url, {})

    def stop_charging(self):
        self.wake()
        url = f"{self._api_url}/vehicles/{self._vehicle_id}/command/charge_stop"

        l.info("Stopped chargiging.")
        self._post(url, {})
        self._post(url, {})

    def get_vehicle_data(self):
        self.wake()
        url = f"{self._api_url}/vehicles/{self._vehicle_id}/vehicle_data"

        r = self._get(url, {})

        return r.json()['response']

    def get_charge_level(self):
        self.wake()
        charging_stats = self.get_charging_stats()

        return charging_stats['battery_level']

    def get_charging_stats(self):
        self.wake()
        url = f"{self._api_url}/vehicles/{self._vehicle_id}/data_request/charge_state"

        r = self._get(url, {})

        return r.json()['response']

    def get_init_charging_amps(self):
        return self.__init_charging_stats['charge_current_request']

    def get_last_charging_amps(self):
        charging_amps = None

        if os.path.exists(self.__latest_stats_file):
            timestamp = os.path.getmtime(self.__latest_stats_file)

            if self.__latest_charging_stats:
                if (time.time() - timestamp) <= 900:
                    charging_amps = self.__latest_charging_stats['charge_current_request']
                    l.info(f"Found viable last charging amps of {charging_amps}.")

        return charging_amps

    def get_charging_amps(self):
        charging_stats = self.get_charging_stats()

        return charging_stats['charge_current_request']

    def get_vehicle_ll(self):
        vdata = self.get_vehicle_data()

        return { 'lat' : vdata['drive_state']['latitude'], 'lon' : vdata['drive_state']['longitude'] }

    def is_home(self, home_address):
        ll = self.get_vehicle_ll()

        home = False
        street_address = self._geoapify.get_street_address(ll['lat'], ll['lon'])

        if street_address == home_address:
            home = True

        return home

    def is_connected(self):
        connected = True
        charging_stats = self.get_charging_stats()

        if charging_stats['charging_state'] == 'Disconnected':
            connected = False

        return connected

    def is_charged(self):
        charged = False
        charging_stats = self.get_charging_stats()

        if charging_stats['battery_level'] >= charging_stats['charge_limit_soc']:
            charged = True
        elif charging_stats['charging_state'] == 'Complete':
            charged = True

        return charged

    def is_charging(self):
        charging = False
        charging_stats = self.get_charging_stats()

        if charging_stats['charging_state'] == 'Charging':
            charging = True

        return charging

class TeslaSelector(TeslaBaseClass):
    def __init__(self, geoapify, token_file):
        TeslaBaseClass.__init__(self, geoapify, token_file)

        self.__interfaces = {}
        self.__vehicles = {}

        self.__init_interfaces()
        self.__selected = None

    def __init_interfaces(self):
        vehicles = self.get_vehicles()

        for row in vehicles:
            vehicle_id = row['id']

            self.__vehicles[vehicle_id] = row

            l.info(f"Found vehicle named {row['display_name']} [{row['id']}].")

            self.__interfaces[vehicle_id] = TeslaInterface(vehicle_id, self._geoapify, self._token_file)

    def select_vehicle(self, home_address):
        candidate_vehicles = []

        for id in self.__vehicles:
            if not self.__interfaces[id].is_home(home_address):
                continue

            if not self.__interfaces[id].is_connected():
                continue

            self.__vehicles[id]['charge_level'] = self.__interfaces[id].get_charge_level()
            candidate_vehicles.append(self.__vehicles[id])

        candidates_sorted = sorted(candidate_vehicles, key=lambda d: d['charge_level'])
        count = len(candidates_sorted)

        if count > 0:
            last_selected = self.__selected
            self.__selected = self.__interfaces[candidates_sorted[0]['id']]

            if self.__selected != last_selected:
                l.info(f"Selected {candidates_sorted[0]['display_name']} [{candidates_sorted[0]['id']}] @ {candidates_sorted[0]['charge_level']}% charge level.")
                if last_selected:
                    if last_selected.is_charging():
                        last_selected.stop_charging()
                    last_selected.reset_charge_configuration()

        return self.__selected
