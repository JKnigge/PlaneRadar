import os
from dotenv import load_dotenv
from luma.core.interface.serial import i2c
from luma.emulator.device import pygame
from luma.lcd.device import hd44780  # For real LCD screen
from luma.core.render import canvas
from PIL import ImageFont


def main():
    # Load environment variables from .env file
    load_dotenv()

    # Get the environment setting
    env = os.getenv('ENVIRONMENT', 'development')  # Default to 'development'

    # Set up the device depending on the environment
    if env == 'development':
        # Use the pygame emulator for development
        device = pygame(width=128, height=64, rotate=0)
    else:
        # Use the real LCD screen via I2C on Raspberry Pi
        serial = i2c(port=1, address=0x27)  # Adjust parameters for your screen
        device = hd44780(serial, width=16, height=2)

    # Load a font (optional)
    font = ImageFont.load_default()

    while True:
    # Display some text on the screen
        with canvas(device) as draw:
            draw.text((10, 20), "Hello, World!", font=font, fill="white")

        # Keep the emulator window open (for pygame emulator only)
        if env == 'development':
            device.show()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
