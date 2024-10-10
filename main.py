import os
from pathlib import Path

from dotenv import load_dotenv
from luma.core.interface.serial import i2c
from luma.emulator.device import pygame
from luma.oled.device import sh1106  # For real LCD screen
from luma.core.render import canvas
from PIL import ImageFont


def main():

    env = get_environment()

    device = get_device(env)

    default_font = ImageFont.load_default()
    awesome_font = make_font("fontawesome-webfont.ttf", 12)

    while True:
        with canvas(device) as draw:
            draw.text((10, 20), "\uf072", font=awesome_font, fill="white")
            draw.text((25, 20), "Hello, World!", font=default_font, fill="white")

        if env == 'development':
            device.show()


def get_device(env):
    if env == 'development':
        device = pygame(width=128, height=64, rotate=0)
    else:
        serial = i2c(port=1, address=0x3C)
        device = sh1106(serial)
    return device


def get_environment():
    load_dotenv()
    env = os.getenv('ENVIRONMENT', 'development')
    return env


def make_font(name, size):
    font_path = str(Path(__file__).resolve().parent.joinpath('fonts', name))
    return ImageFont.truetype(font_path, size)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
