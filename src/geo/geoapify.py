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

import requests
import urllib
import json
import logging
import pprint

from timezonefinder import TimezoneFinder

l = logging.getLogger('helios')

class GeoapifyAPI():
    def __init__(self, api_url, api_key):
        self.__api_url = api_url
        self.__api_key = api_key

    def __get(self, url, params):
        path = urllib.parse.urlparse(url).path
        r = requests.get(url, params)

        if r.status_code == 200:
            l.debug(f"Geoapify API GET {path} => {r}")
        else:
            l.error(f"Geoapify API GET {path} => {r}")

        return r.json()

    def get_street_address(self, lat, lon):
        url = f"{self.__api_url}/geocode/reverse"

        params = { 'lat'    : lat,
                   'lon'    : lon,
                   'apiKey' : self.__api_key }

        json_r = self.__get(url, params)

        return json_r['features'][0]['properties']['address_line1']

    def get_lat_lon(self, street, city, state, postcode):
        url = f"{self.__api_url}/geocode/search"

        params = { 'street'   : street,
                   'city'     : city,
                   'state'    : state,
                   'postcode' : postcode,
                   'apiKey'   : self.__api_key }

        json_r = self.__get(url, params)

        ll = { 'lon' : json_r['features'][0]['properties']['lon'],
               'lat' : json_r['features'][0]['properties']['lat'] }

        return ll

    def get_timezone(self, street, city, state, postcode):
        ll = self.get_lat_lon(street, city, state, postcode)

        tzf = TimezoneFinder()

        return tzf.timezone_at(lat=ll['lat'], lng=ll['lon'])
