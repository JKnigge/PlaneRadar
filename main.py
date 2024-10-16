import csv
import datetime
import os
from io import StringIO
from pathlib import Path
import socket

import requests
from dotenv import load_dotenv
from luma.core.interface.serial import i2c
from luma.emulator.device import pygame
from luma.oled.device import sh1106  # For real LCD screen
from luma.core.render import canvas
from PIL import ImageFont
from math import radians, sqrt, atan2, cos

from SBSMessage import SBSMessage
from database_models import Callsigns, Positions

SCREEN_TIME_IN_SECONDS = 5

R0 = 6371.0

closest_aircraft = None


def get_device(env):
    if env == 'development':
        device = pygame(width=128, height=64, rotate=0)
    else:
        serial = i2c(port=1, address=0x3C)
        device = sh1106(serial)
    return device


def make_font(name, size):
    font_path = str(Path(__file__).resolve().parent.joinpath('fonts', name))
    return ImageFont.truetype(font_path, size)


def read_aircraft_data(file_content):
    return dict(
        (
            line["icao24"],
            {
                "registration": line["registration"],
                "typecode": line["typecode"],
                "operator": line["operatoricao"]
            }
        ) for line in csv.DictReader(file_content) if line["icao24"] != ""
    )


def load_aircraft_data():
    url = "https://opensky-network.org/datasets/metadata/aircraftDatabase.csv"

    # Path to the fallback local CSV file
    local_file = "aircraftDatabase.csv"

    try:
        # Attempt to fetch the CSV content from the online source
        response = requests.get(url)

        if response.status_code == 200:
            csv_content = StringIO(response.text)
            return read_aircraft_data(csv_content)
        else:
            print(f"Failed to fetch the CSV file. Status code: {response.status_code}")
            with open(local_file, "r") as f:
                return read_aircraft_data(f)

    except requests.exceptions.RequestException as e:
        # Handle request errors (e.g., network issues)
        print(f"An error occurred: {e}")
        # Fallback to the local file
        with open(local_file, "r") as f:
            return read_aircraft_data(f)


def handle_transmission_type_1(message: SBSMessage):
    callsign = get_last_callsign_during_last_hour_for(message.hex_ident)
    if callsign is None:
        callsign = create_callsign_entry(message)
    callsign.last_message_generated = message.get_generated_datetime()
    callsign.last_message_received = datetime.datetime.now()
    callsign.num_messages = callsign.num_messages + 1
    callsign.save()


def create_callsign_entry(message: SBSMessage) -> Callsigns:
    callsign = Callsigns(
        hex_ident=message.hex_ident,
        callsign=message.callsign,
        first_message_generated=message.get_generated_datetime(),
        first_message_received=datetime.datetime.now(),
        registration=message.registration,
        typecode=message.typecode,
        operator=message.operator,
        num_messages=0
    )
    return callsign


def handle_transmission_type_3(message: SBSMessage):
    callsign = get_last_callsign_during_last_hour_for(message.hex_ident)
    if callsign is None:
        return
    try:
        plane_postion_in_radians = (radians(float(message.latitude)), radians(float(message.longitude)))
        observer_position = get_observer_location_in_degrees()
        position = Positions(
            hex_ident=message.hex_ident,
            callsign_id=callsign.id,
            latitude=message.latitude,
            longitude=message.longitude,
            altitude=message.altitude,
            distance=calculate_distance(plane_postion_in_radians, observer_position),
            bearing=calculate_bearing(plane_postion_in_radians, observer_position),
            message_generated=message.get_generated_datetime()
        )
        position.save()
        save_closest_aircraft(position)

    except ValueError:
        pass


def get_last_callsign_during_last_hour_for(hex_ident: str) -> Callsigns:
    one_hour_ago = datetime.datetime.now() - datetime.timedelta(hours=1)
    return (Callsigns
            .select()
            .where((Callsigns.hex_ident == hex_ident) & (Callsigns.last_message_received > one_hour_ago))
            .order_by(Callsigns.last_message_received.desc())
            .first())


def calculate_distance(plane_postion_in_radians: (float, float), observer_position: (float, float)) -> float:
    F0 = cos(observer_position[0])  # local conversion for spherical coordinates
    distance = round(R0 * sqrt((plane_postion_in_radians[0] - observer_position[0]) ** 2 + F0 ** 2 * (
            plane_postion_in_radians[1] - observer_position[1]) ** 2), 2)
    return distance


def calculate_bearing(plane_postion_in_radians: (float, float), observer_position: (float, float)) -> float:
    F0 = cos(observer_position[0])  # local conversion for spherical coordinates
    bearing = round(atan2(plane_postion_in_radians[0] - observer_position[0],
                          F0 * (plane_postion_in_radians[1] - observer_position[1])), 2)
    return bearing


def get_observer_location_in_degrees() -> (float, float):
    latitude = float(os.getenv('LATITUDE', 50.036))
    longitude = float(os.getenv('LONGITUDE', 8.553))
    return radians(latitude), radians(longitude)


def save_closest_aircraft(position_message: Positions):
    global closest_aircraft
    if (closest_aircraft is None
            or closest_aircraft.hex_ident == position_message.hex_ident
            or distance_adjusted_by_altitude_penalty(position_message) < distance_adjusted_by_altitude_penalty(closest_aircraft)):
        closest_aircraft = position_message


def distance_adjusted_by_altitude_penalty(position_message: Positions) -> bool:
    return position_message.distance if int(position_message.altitude) < 10000 else position_message.distance + 20


def display_closest_aircraft():
    global closest_aircraft
    if closest_aircraft is None:
        return
    callsign = get_last_callsign_during_last_hour_for(closest_aircraft.hex_ident)
    if callsign is None:
        return
    write_on_screen(callsign, closest_aircraft)


def write_on_screen(callsign: Callsigns, position: Positions):
    env = os.getenv('ENVIRONMENT', 'development')

    device = get_device(env)

    font_normal = make_font("DejaVuSansMono.ttf", 10)
    font_bold = make_font("DejaVuSansMono-Bold.ttf", 12)
    awesome_font = make_font("fontawesome-webfont.ttf", 12)

    with canvas(device) as draw:
        draw.text((5, 0), "\uf072", font=awesome_font, fill="white")
        draw.text((20, 0), callsign.callsign, font=font_bold, fill="white")
        draw.text((5, 15), f"Alt: {position.altitude} ft", font=font_normal, fill="white")
        draw.text((5, 25), f"Dist: {position.distance} km", font=font_normal, fill="white")
        draw.text((5, 35), f"Type: {callsign.typecode}", font=font_normal, fill="white")
        draw.text((5, 45), f"Reg: {callsign.registration}", font=font_normal, fill="white")

    if env == 'development':
        device.show()


def main():
    try:
        load_dotenv()
        aircraft_data = load_aircraft_data()

        HOST = os.getenv("1090_HOST")
        PORT = int(os.getenv("1090_PORT"))

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))

            while True:
                data = s.recv(1024)
                if not data:
                    break
                raw_message = data.decode('utf-8')
                message = SBSMessage(raw_message, aircraft_data)
                if message.message_type == "MSG" and message.transmission_type == '1':
                    print(raw_message)
                    handle_transmission_type_1(message)
                elif message.message_type == "MSG" and message.transmission_type == '3':
                    print(raw_message)
                    handle_transmission_type_3(message)
                    display_closest_aircraft()

    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
