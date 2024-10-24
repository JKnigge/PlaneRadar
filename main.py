import argparse
import csv
import datetime
import math
import os
from io import StringIO
from pathlib import Path
import socket

import requests
from PIL import ImageDraw, Image
from dotenv import load_dotenv
from luma.core.interface.serial import i2c
from luma.emulator.device import pygame
from luma.oled.device import sh1106  # For real LCD screen
from PIL import ImageFont
from math import radians, sqrt, atan2, cos

from SBSMessage import SBSMessage
from database_models import Callsigns, Positions

R0 = 6371.0
PREF_ALT_LIMIT_IN_FEET = 15000  #planes below this altitude will be preferred for the display.

closest_aircraft = None
last_screen_update = None


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


def get_aircraft_data(download_file: bool):
    if download_file:
        print("Downloading...")
        return download_aircraft_data()
    else:
        print("Taking local file...")
        local_file = "aircraftDatabase.csv"
        with open(local_file, "r") as f:
            return read_aircraft_data(f)

def download_aircraft_data():
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
    callsign.registration = message.registration
    callsign.typecode = message.typecode
    callsign.operator = message.operator
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
        distance = calculate_distance(plane_postion_in_radians, observer_position)
        bearing = calculate_bearing(plane_postion_in_radians, observer_position)
        position_0 = Positions.select().where(Positions.callsign_id == callsign.id).first()
        if position_0 is None:
            create_position_entry(callsign, message, distance, bearing, 0)
        else:
            position_i = Positions.select().where(
                (Positions.callsign_id == callsign.id) & (Positions.num_message > 0)).first()
            if position_i is None:
                create_position_entry(callsign, message, distance, bearing,1)
            else:
                update_position_entry(position_i, message, distance, bearing)
        save_closest_distance(callsign, distance)
        save_lowest_altitude(callsign, int(message.altitude))

    except ValueError:
        pass


def save_closest_distance(callsign: Callsigns, distance: float):
    if callsign.closest_dist is None or callsign.closest_dist > distance:
        callsign.closest_dist = distance
        callsign.save()


def save_lowest_altitude(callsign: Callsigns, height: int):
    if callsign.lowest_alt is None or callsign.lowest_alt > height:
        callsign.lowest_alt = height
        callsign.save()

def update_position_entry(position: Positions, message: SBSMessage, distance: float, bearing: float):
    try:
        position.hex_ident = message.hex_ident
        position.latitude = message.latitude
        position.longitude = message.longitude
        position.altitude = message.altitude
        position.distance = distance
        position.bearing = bearing
        position.message_generated = message.get_generated_datetime()
        position.num_message = position.num_message + 1

        position.save()
        save_closest_aircraft(position)

    except ValueError:
        pass


def create_position_entry(callsign: Callsigns, message: SBSMessage, distance: float, bearing: float, num: int):
    try:
        position = Positions(
            hex_ident=message.hex_ident,
            callsign_id=callsign.id,
            latitude=message.latitude,
            longitude=message.longitude,
            altitude=message.altitude,
            distance=distance,
            bearing=bearing,
            message_generated=message.get_generated_datetime(),
            num_message=num
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


def calculate_bearing(plane_position_in_radians: (float, float), observer_position: (float, float)) -> float:
    delta_lat = plane_position_in_radians[0] - observer_position[0]
    delta_lon = plane_position_in_radians[1] - observer_position[1]
    F0 = math.cos(observer_position[0])

    bearing_rad = math.atan2(delta_lon * F0, delta_lat)
    return bearing_rad


def get_observer_location_in_degrees() -> (float, float):
    latitude = float(os.getenv('LATITUDE', 50.036))
    longitude = float(os.getenv('LONGITUDE', 8.553))
    return radians(latitude), radians(longitude)


def save_closest_aircraft(position_message: Positions):
    global closest_aircraft
    if (closest_aircraft is None
            or closest_aircraft.hex_ident == position_message.hex_ident
            or distance_adjusted_by_altitude_penalty(position_message) < distance_adjusted_by_altitude_penalty(
                closest_aircraft)):
        closest_aircraft = position_message


def distance_adjusted_by_altitude_penalty(position_message: Positions) -> bool:
    return position_message.distance if int(
        position_message.altitude) < PREF_ALT_LIMIT_IN_FEET else position_message.distance + 20


def update_screen(screentime_in_seconds: int):
    global last_screen_update

    if screentime_in_seconds < 1:
        display_closest_aircraft()
        return

    if last_screen_update is None:
        last_screen_update = datetime.datetime.now()
        display_closest_aircraft()
        return

    time_now = datetime.datetime.now()
    timediff = time_now - last_screen_update

    if timediff > datetime.timedelta(seconds=screentime_in_seconds):
        last_screen_update = time_now
        display_closest_aircraft()


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

    image = Image.new('1', (device.width, device.height))
    draw = ImageDraw.Draw(image)

    draw.text((5, 0), "\uf072", font=awesome_font, fill="white")
    draw.text((20, 0), callsign.callsign, font=font_bold, fill="white")
    draw.text((5, 15), f"Alt: {position.altitude} ft", font=font_normal, fill="white")
    draw.text((5, 25), f"Dist: {position.distance} km", font=font_normal, fill="white")
    draw.text((5, 35), f"Type: {callsign.typecode}", font=font_normal, fill="white")
    draw.text((5, 45), f"Reg: {callsign.registration}", font=font_normal, fill="white")
    draw_small_compass(draw, 110, 40, position.bearing)

    device.display(image)

    if env == 'development':
        device.show()


def draw_small_compass(draw, center_x, center_y, bearing_rad):
    radius = 12
    arrow_length = 4

    font = make_font("DejaVuSansMono.ttf", 10)

    draw.ellipse((center_x - radius, center_y - radius, center_x + radius, center_y + radius), outline="white")

    for angle in range(0, 360, 90):
        angle_rad = math.radians(angle)

        outer_x = center_x + (radius + 1) * math.sin(angle_rad)
        outer_y = center_y - (radius + 1) * math.cos(angle_rad)

        inner_x = center_x + (radius - 3) * math.sin(angle_rad)
        inner_y = center_y - (radius - 3) * math.cos(angle_rad)

        draw.line((inner_x, inner_y, outer_x, outer_y), fill="white", width=1)

        arrow_x = center_x + (radius + arrow_length) * math.sin(bearing_rad)
        arrow_y = center_y - (radius + arrow_length) * math.cos(bearing_rad)

        draw.line((center_x + (radius - 1) * math.sin(bearing_rad),
                   center_y - (radius - 1) * math.cos(bearing_rad),
                   arrow_x, arrow_y), fill="white", width=1)

    draw.text((center_x - 3, center_y - radius - 12), "N", fill="white", font=font)

    bearing_deg = round(math.degrees(bearing_rad) % 360, 2)
    bearing_text = to_string_with_leading_zero(int(bearing_deg))

    text_bbox = draw.textbbox((0, 0), bearing_text, font=font)
    text_width = text_bbox[2] - text_bbox[0]

    draw.text((center_x - text_width // 2, center_y - 10 // 2), bearing_text, fill="white", font=font)


def to_string_with_leading_zero(number: int) -> str:
    output = ""
    if number < 10:
        output = output + "0"
    if number < 100:
        output = output + "0"
    return output + str(number)


def main(download_file: bool, screentime: int):
    try:
        load_dotenv()
        aircraft_data = get_aircraft_data(download_file)

        HOST = os.getenv("1090_HOST")
        PORT = int(os.getenv("1090_PORT"))

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            with s.makefile() as f:
                while True:
                    raw_message = f.readline()
                    if not raw_message:
                        break
                    message = SBSMessage(raw_message, aircraft_data)
                    if message.message_type == "MSG" and message.transmission_type == '1':
                        print(raw_message)
                        handle_transmission_type_1(message)
                    elif message.message_type == "MSG" and message.transmission_type == '3':
                        print(raw_message)
                        handle_transmission_type_3(message)
                        update_screen(screentime)

    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Downloads the aircraft database file or uses a local copy. Updates the screen display.")

    parser.add_argument(
        "-d", "--download",
        action="store_true",
        help="Download the aircrafDatabase file before running"
    )
    parser.add_argument(
        "-s", "--screentime",
        type=int,
        default=2,
        help="Set the wait time in seconds between screen refreshs. Can also be set to 0 for immediate refresh (default: 2)."
    )

    args = parser.parse_args()

    main(args.download, args.screentime)
