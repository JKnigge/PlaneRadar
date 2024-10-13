import csv
import os
from io import StringIO
from pathlib import Path

import requests
from dotenv import load_dotenv
from luma.core.interface.serial import i2c
from luma.emulator.device import pygame
from luma.oled.device import sh1106  # For real LCD screen
from luma.core.render import canvas
from PIL import ImageFont
from time import time, sleep
from math import radians, sqrt, atan2, cos

SCREEN_TIME_IN_SECONDS = 5

R0 = 6371.0

RAW_MESSAGE_FORMAT = [
    "Message type",
    "Transmission Type",
    "Session ID",
    "AircraftID",
    "HexIdent",
    "FlightID",
    "Date message generated",
    "Time message generated",
    "Date message logged",
    "Time message logged",
    "Callsign",
    "Altitude",
    "GroundSpeed",
    "Track",
    "Latitude",
    "Longitude",
    "VerticalRate",
    "Squawk",
    "Alert",
    "Emergency",
    "SPI",
    "IsOnGround"
]


def get_observer_location_in_degrees():
    latitude = float(os.getenv('LATITUDE', 50.036))
    longitude = float(os.getenv('LONGITUDE', 8.553))
    return (radians(latitude), radians(longitude))

def write_on_screen(message):
    env = os.getenv('ENVIRONMENT', 'development')

    device = get_device(env)

    font_normal = make_font("DejaVuSansMono.ttf", 10)
    font_bold = make_font("DejaVuSansMono-Bold.ttf", 12)
    awesome_font = make_font("fontawesome-webfont.ttf", 12)

    with canvas(device) as draw:
        draw.text((5, 0), "\uf072", font=awesome_font, fill="white")
        draw.text((20, 0), "LH9200", font=font_bold, fill="white")
        draw.text((5, 15), f"Height: {message['altitude']} ft", font=font_normal, fill="white")
        draw.text((5, 25), f"Distance: {message['distance']} m", font=font_normal, fill="white")
        draw.text((5, 35), f"Type: {message['typecode']}", font=font_normal, fill="white")

    if env == 'development':
        device.show()

    sleep(SCREEN_TIME_IN_SECONDS)

    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="black", fill="black")


def process_message(raw_message, aircraft_data):
    message = dict(zip(RAW_MESSAGE_FORMAT, raw_message.split(",")))
    processed_message = {"processing_time": int(time() * 1000)}
    observer_position = get_observer_location_in_degrees()

    # local conversion for spherical coordinates
    F0 = cos(observer_position[0])

    if "HexIdent" in message:
        icao_address = message["HexIdent"]
        processed_message["address"] = icao_address
        try:
            record = aircraft_data[icao_address.lower()]
            processed_message["registration"] = record["registration"]
            processed_message["typecode"] = record["typecode"]
            processed_message["operator"] = record["operator"]
        except KeyError:
            pass

    if "Latitude" in message and "Longitude" in message:
        try:
            x = (radians(float(message["Latitude"])), radians(float(message["Longitude"])))
            processed_message["distance"] = round(R0 * sqrt((x[0] - observer_position[0]) ** 2 + F0 ** 2 * (x[1] - observer_position[1]) ** 2), 2)
            processed_message["bearing"] = round(atan2(x[0] - observer_position[0], F0 * (x[1] - observer_position[1])), 2)
        except ValueError:
            pass

    if "Altitude" in message:
        try:
            processed_message["altitude"] = int(message["Altitude"])
        except ValueError:
            pass

    if "FlightID" in message:
        try:
            processed_message["flight_id"] = message["FlightID"]
        except ValueError:
            pass

    return processed_message


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


if __name__ == "__main__":
    try:
        load_dotenv()
        aircraft_data = load_aircraft_data()
        while True:
            print("Please input:")
            raw_message = input()
            print("Processing input")
            processed_message = process_message(raw_message, aircraft_data)
            write_on_screen(processed_message)
    except KeyboardInterrupt:
        pass
