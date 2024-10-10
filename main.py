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

    font_normal = make_font("DejaVuSansMono.ttf", 10)
    font_bold = make_font("DejaVuSansMono-Bold.ttf", 12)
    awesome_font = make_font("fontawesome-webfont.ttf", 12)

    while True:
        with canvas(device) as draw:
            draw.text((5, 0), "\uf072", font=awesome_font, fill="white")
            draw.text((20, 0), "LH9200", font=font_bold, fill="white")
            draw.text((5, 15), "Height: 15400 ft", font=font_normal, fill="white")
            draw.text((5, 25), "Distance: 15300 m", font=font_normal, fill="white")
            draw.text((5, 35), "Type: B773", font=font_normal, fill="white")

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
