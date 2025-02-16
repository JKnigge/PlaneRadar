import argparse
import concurrent.futures
import csv
import datetime
import math
import os
import time
import traceback
from collections import deque
from io import StringIO
from pathlib import Path
import socket

import requests
from dotenv import load_dotenv
from luma.core.interface.serial import i2c
from luma.emulator.device import pygame
from luma.oled.device import sh1106  # For real LCD screen
from PIL import ImageFont
from math import radians, sqrt, cos
from PIL import ImageDraw, Image

from SBSMessage import SBSMessage
from database_models import Callsigns, Positions

###############################################################################################
# Global Settings
###############################################################################################

# Pins
SCREEN_SWITCH_PIN = 23
LOW_ALT_PRIO_SWITCH_PIN = 24
LED_YELLOW_PIN = 27
LED_GREEN_PIN = 17

# Dev values:
DEV_SCREEN_SWITCH_STATE = True
DEV_LOW_ALT_PRIO_SWITCH_STATE = False

# Other Values
R0 = 6371.0
PREF_ALT_LIMIT_IN_FEET = 15000  # planes below this altitude will be preferred for the display.
MAX_MESSAGE_READ_RETRIES = 5
SERVER_URL = "http://127.0.0.1:8000/update"
CALLSIGNS_LIST_MAX_LEN = 30

###############################################################################################
# Program Code
###############################################################################################

closest_aircraft: Positions | None = None
closest_aircraft_low_alt: Positions | None = None
closest_aircraft_callsign: Callsigns | None = None
closest_aircraft_low_alt_callsign: Callsigns | None = None
last_screen_update: datetime.datetime | None = None
was_screen_on: bool = False
last_low_alt_prio_switch_state: bool = False
callsigns: deque[Callsigns] = deque()

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT")

if ENVIRONMENT == "development":
    import Mock.GPIO as GPIO
else:
    import RPi.GPIO as GPIO

GPIO.cleanup()
GPIO.setmode(GPIO.BCM)
GPIO.setup(SCREEN_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(LOW_ALT_PRIO_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(LED_YELLOW_PIN, GPIO.OUT)
GPIO.setup(LED_GREEN_PIN, GPIO.OUT)

if ENVIRONMENT == 'development':
    device = pygame(width=128, height=64, rotate=0)
else:
    serial = i2c(port=1, address=0x3C)
    device = sh1106(serial)


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
    callsign = get_callsign_from_list(message)
    if callsign is None:
        callsign = create_callsign_entry(message)
        callsign.save()
        print(f"Callsign added (id: {callsign.id}, hex_ident: {callsign.hex_ident}, callsign: {callsign.callsign}).")
        add_callsign_to_list(callsign)
    callsign.last_message_generated = message.get_generated_datetime()
    callsign.last_message_received = datetime.datetime.now()
    callsign.num_messages = callsign.num_messages + 1
    callsign.registration = message.registration
    callsign.registration = message.registration
    callsign.typecode = message.typecode
    callsign.operator = message.operator


def get_callsign_from_list(message) -> Callsigns | None:
    global callsigns
    callsigns_matching_message = [c for c in callsigns if c.hex_ident == message.hex_ident]
    callsign = callsigns_matching_message[-1] if callsigns_matching_message else None
    one_hour_ago = datetime.datetime.now() - datetime.timedelta(hours=1)
    if callsign is None or callsign.last_message_generated < one_hour_ago:
        return None
    return callsign


def add_callsign_to_list(callsign: Callsigns):
    global callsigns
    if len(callsigns) >= CALLSIGNS_LIST_MAX_LEN:
        removed_callsign = callsigns.popleft()
        removed_callsign.save()
    callsigns.append(callsign)


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


def handle_transmission_type_3(message: SBSMessage) -> bool:
    global closest_aircraft, closest_aircraft_low_alt, closest_aircraft_callsign, closest_aircraft_low_alt_callsign
    try:
        plane_position_in_radians = (radians(float(message.latitude)), radians(float(message.longitude)))
        observer_position = get_observer_location_in_degrees()
        distance = calculate_distance(plane_position_in_radians, observer_position)
        altitude = int(message.altitude)
        is_closest = is_plane_closer(message.hex_ident, distance)
        is_closest_low_alt = is_plane_closer_low_alt(message.hex_ident, distance, altitude)
        if is_closest or is_closest_low_alt:
            callsign = get_callsign(closest_aircraft_callsign, closest_aircraft_low_alt_callsign, message)
            if callsign is None:
                return False
            bearing = calculate_bearing(plane_position_in_radians, observer_position)
            position = create_or_update_position(bearing, callsign, distance, message)
            print(f"Position added or updated (id: {position.id}, hex_ident: {position.hex_ident}, callsign_id: {position.callsign_id}).")
            if is_closest:
                closest_aircraft = position
                closest_aircraft_callsign = callsign
            if is_closest_low_alt:
                closest_aircraft_low_alt = position
                closest_aircraft_low_alt_callsign = callsign
            save_closest_distance(callsign, distance)
            save_lowest_altitude(callsign, int(message.altitude))
            return True
        return False

    except ValueError:
        pass


def create_or_update_position(bearing: float, callsign: Callsigns, distance: float, message: SBSMessage) -> Positions:
    position_0 = Positions.select().where(Positions.callsign_id == callsign.id).first()
    if position_0 is None:
        position = create_position_entry(callsign, message, distance, bearing, 0)
    else:
        position_i = Positions.select().where(
            (Positions.callsign_id == callsign.id) & (Positions.num_message > 0)).first()
        if position_i is None:
            position = create_position_entry(callsign, message, distance, bearing, 1)
        else:
            position = update_position_entry(position_i, message, distance, bearing)
    return position


def get_callsign(closest_callsign, closest_low_alt_callsign, message) -> Callsigns | None:
    if closest_callsign is not None and closest_callsign.hex_ident == message.hex_ident:
        callsign = closest_callsign
    elif closest_low_alt_callsign is not None and closest_low_alt_callsign == message.hex_ident:
        callsign = closest_low_alt_callsign
    else:
        callsign = get_callsign_from_list(message)
    return callsign


def save_closest_distance(callsign: Callsigns, distance: float):
    if callsign.closest_dist is None or callsign.closest_dist > distance:
        callsign.closest_dist = distance
        callsign.save()


def save_lowest_altitude(callsign: Callsigns, height: int):
    if callsign.lowest_alt is None or callsign.lowest_alt > height:
        callsign.lowest_alt = height
        callsign.save()


def update_position_entry(position: Positions, message: SBSMessage, distance: float, bearing: float) -> Positions:
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

        return position

    except ValueError:
        pass


def create_position_entry(callsign: Callsigns, message: SBSMessage, distance: float, bearing: float,
                          num: int) -> Positions:
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
        return position

    except ValueError:
        pass


def get_last_callsign_during_last_hour_for(hex_ident: str) -> Callsigns:
    one_hour_ago = datetime.datetime.now() - datetime.timedelta(hours=1)
    return (Callsigns
            .select()
            .where((Callsigns.hex_ident == hex_ident) & (Callsigns.last_message_received > one_hour_ago))
            .order_by(Callsigns.last_message_received.desc())
            .first())


def calculate_distance(plane_position_in_radians: (float, float), observer_position: (float, float)) -> float:
    f0 = cos(observer_position[0])  # local conversion for spherical coordinates
    distance = round(R0 * sqrt((plane_position_in_radians[0] - observer_position[0]) ** 2 + f0 ** 2 * (
            plane_position_in_radians[1] - observer_position[1]) ** 2), 2)
    return distance


def calculate_bearing(plane_position_in_radians: (float, float), observer_position: (float, float)) -> float:
    delta_lat = plane_position_in_radians[0] - observer_position[0]
    delta_lon = plane_position_in_radians[1] - observer_position[1]
    f0 = math.cos(observer_position[0])

    bearing_rad = math.atan2(delta_lon * f0, delta_lat)
    return bearing_rad


def get_observer_location_in_degrees() -> (float, float):
    latitude = float(os.getenv('LATITUDE', 50.036))
    longitude = float(os.getenv('LONGITUDE', 8.553))
    return radians(latitude), radians(longitude)


def is_plane_closer(hex_ident: str, distance: float) -> bool:
    global closest_aircraft
    if closest_aircraft is None or closest_aircraft.hex_ident == hex_ident:
        return True
    if distance < closest_aircraft.distance:
        return True
    return False


def is_plane_closer_low_alt(hex_ident: str, distance: float, altitude: int) -> bool:
    global closest_aircraft_low_alt
    if closest_aircraft_low_alt is None or closest_aircraft_low_alt.hex_ident == hex_ident:
        return True
    if distance_adjusted_by_altitude_penalty(distance, altitude) < distance_adjusted_by_altitude_penalty(
            closest_aircraft_low_alt.distance, int(closest_aircraft_low_alt.altitude)):
        return True
    return False


def distance_adjusted_by_altitude_penalty(distance: float, altitude: int) -> float:
    return distance if altitude < PREF_ALT_LIMIT_IN_FEET else distance + 20


def clear_screen():
    global device
    device.clear()
    device.show()


def show_on_screen(screentime_in_seconds: int, keepon: bool, low_alt_prio_switch_state: bool):
    global last_screen_update

    if screentime_in_seconds < 1:
        display_closest_aircraft(keepon, low_alt_prio_switch_state)
        return

    if last_screen_update is None:
        last_screen_update = datetime.datetime.now()
        display_closest_aircraft(keepon, low_alt_prio_switch_state)
        return

    time_now = datetime.datetime.now()
    timediff = time_now - last_screen_update

    if timediff > datetime.timedelta(seconds=screentime_in_seconds):
        last_screen_update = time_now
        display_closest_aircraft(keepon, low_alt_prio_switch_state)


def display_closest_aircraft(keepon: bool, low_alt_prio_switch_state: bool):
    global closest_aircraft, closest_aircraft_low_alt, closest_aircraft_callsign, closest_aircraft_low_alt_callsign

    if low_alt_prio_switch_state == GPIO.LOW:
        closest = closest_aircraft_low_alt
        callsign = closest_aircraft_low_alt_callsign
    else:
        closest = closest_aircraft
        callsign = closest_aircraft_callsign
    if closest is None or callsign is None:
        return
    write_on_screen(callsign, closest, keepon, low_alt_prio_switch_state)


def write_on_screen(callsign: Callsigns, position: Positions, keepon: bool, low_alt_prio_switch_state):
    global device

    font_normal = make_font("DejaVuSansMono.ttf", 10)
    font_bold = make_font("DejaVuSansMono-Bold.ttf", 12)
    awesome_font = make_font("fontawesome-webfont.ttf", 12)
    awesome_font_small = make_font("fontawesome-webfont.ttf", 10)

    image = Image.new('1', (device.width, device.height))
    draw = ImageDraw.Draw(image)

    draw.text((5, 1), "\uf072", font=awesome_font, fill="white")
    draw.text((20, 1), create_header(callsign), font=font_bold, fill="white")
    draw.text((5, 15), f"Alt: {position.altitude} ft", font=font_normal, fill="white")
    draw.text((5, 25), f"Dist: {position.distance} km", font=font_normal, fill="white")
    draw.text((5, 35), f"Type: {callsign.typecode}", font=font_normal, fill="white")
    draw.text((5, 50), "\uf017", font=awesome_font_small, fill="white")
    if position.message_received is not None:
        message_timestamp = position.message_received.strftime("%H:%M:%S")
        draw.text((15, 50), f"{message_timestamp} ({position.num_message})", font=font_normal, fill="white")
    draw_small_compass(draw, 110, 40, position.bearing)

    if low_alt_prio_switch_state == GPIO.LOW:
        draw.text((105, 50), "\uf06e", font=awesome_font, fill="white")

    device.display(image)

    if keepon:
        device.command(0xAF)

    if ENVIRONMENT == 'development':
        device.show()


def create_header(callsign: Callsigns) -> str:
    if callsign.registration is None:
        return callsign.callsign
    return f"{callsign.callsign} ({callsign.registration})"


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


def read_switch_input(gpio_pin: int) -> bool:
    if ENVIRONMENT == "development":
        if gpio_pin == SCREEN_SWITCH_PIN:
            return DEV_SCREEN_SWITCH_STATE
        if gpio_pin == LOW_ALT_PRIO_SWITCH_PIN:
            return DEV_LOW_ALT_PRIO_SWITCH_STATE
        else:
            print("Missing value for debug switch state. Using Low (False) state...")
            return False
    else:
        try:
            return GPIO.input(gpio_pin)
        except Exception as e:
            print(f"GPIO error: {e}")
            traceback.print_exc()
            return GPIO.LOW


def turn_only_yellow_led_on():
    GPIO.output(LED_YELLOW_PIN, True)
    GPIO.output(LED_GREEN_PIN, False)


def turn_only_green_led_on():
    GPIO.output(LED_YELLOW_PIN, False)
    GPIO.output(LED_GREEN_PIN, True)


def turn_off_all_led():
    GPIO.output(LED_YELLOW_PIN, False)
    GPIO.output(LED_GREEN_PIN, False)


def broadcast_closest_plane(low_alt_prio_switch_state: bool):
    global closest_aircraft
    if closest_aircraft is None:
        return
    callsign = get_last_callsign_during_last_hour_for(closest_aircraft.hex_ident)
    if callsign is None:
        return
    position: Positions = closest_aircraft
    bearing_deg = round(math.degrees(position.bearing) % 360, 2)
    bearing_text = to_string_with_leading_zero(int(bearing_deg))
    if low_alt_prio_switch_state:
        mode = "ALT PNY off"
    else:
        mode = "ALT PNY on"
    data = {
        "callsign": callsign.callsign,
        "registration": callsign.registration if callsign.registration else "-",
        "altitude": position.altitude if position.altitude else "-",
        "distance": position.distance if position.distance else "-",
        "type": callsign.typecode if callsign.typecode else "-",
        "bearing": bearing_text,
        "timestamp": position.message_received.strftime("%H:%M:%S") if position.message_received else "-",
        "message_num": position.num_message,
        "mode": mode
    }
    send_data_to_server(data)


def send_data_to_server(data):
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.submit(create_post_request, data)
    except requests.exceptions.RequestException as e:
        print(f"Error sending data: {e}")


def create_post_request(data):
    requests.post(SERVER_URL, json=data)


def update_screen_if_status_changed(screen_switch_state: bool, screentime_in_seconds: int, keepon: bool):
    global was_screen_on
    if was_screen_on and screen_switch_state != GPIO.HIGH:
        clear_screen()
        was_screen_on = False
    elif not was_screen_on:
        was_screen_on = True
        low_alt_prio_switch_state = read_switch_input(LOW_ALT_PRIO_SWITCH_PIN)
        show_on_screen(screentime_in_seconds, keepon, low_alt_prio_switch_state)


def process_planedata(download_file: bool, screentime: int, keepon: bool, broadcast: bool):
    global last_low_alt_prio_switch_state
    try:
        turn_only_yellow_led_on()
        aircraft_data = get_aircraft_data(download_file)

        print("Aircraft data loaded.")

        host = os.getenv("1090_HOST")
        port = int(os.getenv("1090_PORT"))

        while True:  # Restart loop if connection is lost
            missing_messages = 0
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((host, port))
                    with s.makefile() as f:
                        while True:
                            turn_only_green_led_on()
                            screen_switch_state = read_switch_input(SCREEN_SWITCH_PIN)
                            update_screen_if_status_changed(screen_switch_state, screentime, keepon)
                            raw_message = f.readline()
                            if not raw_message:
                                missing_messages += 1
                                if missing_messages >= MAX_MESSAGE_READ_RETRIES:
                                    print("Connection lost. Restarting connection...")
                                    break
                                print(
                                    f"Warning: No data received. Retrying (attempt {missing_messages}"
                                    f"/{MAX_MESSAGE_READ_RETRIES})...")
                                continue

                            missing_messages = 0  # Reset on successful read
                            message = SBSMessage(raw_message, aircraft_data)
                            if message.message_type == "MSG" and message.transmission_type == '1':
                                turn_only_yellow_led_on()
                                handle_transmission_type_1(message)
                            elif message.message_type == "MSG" and message.transmission_type == '3':
                                turn_only_yellow_led_on()
                                changed = handle_transmission_type_3(message)
                                low_alt_prio_switch_state = read_switch_input(LOW_ALT_PRIO_SWITCH_PIN)
                                if last_low_alt_prio_switch_state != low_alt_prio_switch_state:
                                    last_low_alt_prio_switch_state = low_alt_prio_switch_state
                                    changed = True
                                if changed and broadcast:
                                    broadcast_closest_plane(low_alt_prio_switch_state)
                                if changed and screen_switch_state == GPIO.HIGH:
                                    show_on_screen(screentime, keepon, low_alt_prio_switch_state)

            except (socket.error, ConnectionError) as conn_error:
                print(f"Socket error: {conn_error}. Retrying in 2 seconds...")
                time.sleep(1)

    except KeyboardInterrupt:
        print("User interrupted execution.")
        raise  # Re-raises the exception so the program terminates properly
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
    finally:
        clear_screen()
        turn_off_all_led()
        GPIO.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Downloads the aircraft database file or uses a local copy. Updates the screen display.")

    parser.add_argument(
        "-d", "--download",
        action="store_true",
        help="Download the aircrafDatabase file before running"
    )
    parser.add_argument(
        "-k", "--keepon",
        action="store_true",
        help="Set to keep the screen on."
    )
    parser.add_argument(
        "-b", "--broadcast",
        action="store_true",
        help="Publish data to server via rest."
    )
    parser.add_argument(
        "-s", "--screentime",
        type=int,
        default=2,
        help="Set the wait time in seconds between screen refreshs. Can also be set to 0 for immediate refresh ("
             "default: 2)."
    )

    args = parser.parse_args()
    process_planedata(args.download, args.screentime, args.keepon, args.broadcast)
