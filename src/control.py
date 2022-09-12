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

import logging
import time

l = logging.getLogger('helios')

class Amperage():
    def __init__(self, enphase, home_battery, reserved_power, start_time):
        self.__enphase = enphase
        self.__home_battery = home_battery
        self.__reserved_power = reserved_power
        self.__start_time = start_time

        self.__prior_target = None
        self.__last_power_check = None
        self.__check_buckets = ( 5, 20, 35, 50 )

    def check_power(self):
        ct = time.time()
        min = time.localtime(ct).tm_min

        if self.__last_power_check:
            if ct - self.__last_power_check <= 60:
                return False

        if min in self.__check_buckets:
            self.__last_power_check = ct
            return True

        return False

    def find_target(self):
        target = None
        power_target = None

        battery = self.__enphase.get_battery_charge()
        if battery['level'] >= self.__home_battery:
            energy = self.__enphase.get_meters()
            total_pwr_produced = energy[-1]['pwr_produced']
            total_pwr_exported = energy[-1]['pwr_exported']
            battery_charged = battery['intervals'][-1]['pwr_charged']
            pwr_produced_change = energy[-1]['pwr_produced'] / energy[-2]['pwr_produced']

            l.debug(f"total power produced: {total_pwr_produced}")
            l.debug(f"total power exported: {total_pwr_exported}")
            l.debug(f"total power to battery: {battery_charged}")
            l.debug(f"change in power produced: {pwr_produced_change}")

            if self.__prior_target:
                l.debug(f"prior target set: {self.__prior_target}")

                sec_since_start = time.time() - self.__start_time
                vehicile_pwr_consumed = 240 * self.__prior_target

                l.debug(f"vehicle power consumed: {vehicile_pwr_consumed}")

                if sec_since_start <= 900:
                    l.debug(f"adjusting vehicle power consumed: ")
                    l.debug(f"{vehicile_pwr_consumed} * {sec_since_start / 900}")

                    vehicile_pwr_consumed = vehicile_pwr_consumed * (sec_since_start / 900)

                l.debug(f"power target: ")
                l.debug(f"(({vehicile_pwr_consumed} + {battery_charged} + {total_pwr_exported})")
                l.debug(f"* {pwr_produced_change}) - {self.__reserved_power}")

                power_target = ((vehicile_pwr_consumed + battery_charged + total_pwr_exported) \
                                 * pwr_produced_change) - self.__reserved_power

                if power_target > total_pwr_produced:
                    l.debug(f"power target greater than produced: {power_target} > {total_pwr_produced}")
                    power_target = total_pwr_produced - self.__reserved_power
                    l.debug(f"power target reset: {power_target}")
            else:
                l.debug(f"no prior target power target: ")
                l.debug(f"(({total_pwr_exported} + {battery_charged})")
                l.debug(f"* {pwr_produced_change}) - {self.__reserved_power}")

                power_target = ((total_pwr_exported + battery_charged) \
                                 * pwr_produced_change) - self.__reserved_power

            l.info(f"Found a power target of {int(power_target)} watts.")
            target = int(power_target / 244)

            if target < 5:
                target = None

            if target:
                l.info(f"Found an amperage target of {target}.")
            else:
                l.info("No reasonable amperage target could be found.")
        else:
            l.info(f"House battery level ({battery['level']}%) too low, no amperage target will be set.")

        self.__prior_target = target

        return target

