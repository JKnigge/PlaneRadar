import os
from dotenv import load_dotenv
from luma.core.interface.serial import i2c
from luma.emulator.device import pygame
from luma.lcd.device import hd44780  # For real LCD screen
from luma.core.render import canvas
from PIL import ImageFont


def main():

    env = get_environment()

    device = get_device(env)

    font = ImageFont.load_default()

    while True:
        with canvas(device) as draw:
            draw.text((10, 20), "Hello, World!", font=font, fill="white")

        if env == 'development':
            device.show()


def get_device(env):
    if env == 'development':
        device = pygame(width=128, height=64, rotate=0)
    else:
        serial = i2c(port=1, address=0x27)
        device = hd44780(serial, width=16, height=2)
    return device


def get_environment():
    load_dotenv()
    env = os.getenv('ENVIRONMENT', 'development')
    return env


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
