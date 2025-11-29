/*!
meshuga/web-spectrum
Copyright (C) 2024 Patryk Orwat

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

export enum Protocol {
    ADSB = 'ADSB',
    GateTX24 = 'GATETX24',
    GNSS_GPS_L1 = 'GNSS_GPS_L1',
    GNSS_GALILEO_E1 = 'GNSS_GALILEO_E1',
    GNSS_GLONASS_L1 = 'GNSS_GLONASS_L1',
    GNSS_BEIDOU_B1I = 'GNSS_BEIDOU_B1I',
}

export const isIsm = (proto: Protocol) =>
    proto !== Protocol.ADSB &&
    proto !== Protocol.GNSS_GPS_L1 &&
    proto !== Protocol.GNSS_GALILEO_E1 &&
    proto !== Protocol.GNSS_GLONASS_L1 &&
    proto !== Protocol.GNSS_BEIDOU_B1I;

export const isGNSS = (proto: Protocol) =>
    proto === Protocol.GNSS_GPS_L1 ||
    proto === Protocol.GNSS_GALILEO_E1 ||
    proto === Protocol.GNSS_GLONASS_L1 ||
    proto === Protocol.GNSS_BEIDOU_B1I;

export const ProtocolToMsgLength: ReadonlyMap<Protocol, number> = new Map([
    [Protocol.ADSB, 120],
    [Protocol.GateTX24, 24],
    [Protocol.GNSS_GPS_L1, 300],
    [Protocol.GNSS_GALILEO_E1, 250],
    [Protocol.GNSS_GLONASS_L1, 100],
    [Protocol.GNSS_BEIDOU_B1I, 300],
])