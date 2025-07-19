# Planeradar

This tool analyzes ADS-B messages from [dump1090](https://github.com/flightaware/dump1090). It processes incoming
messages in [BaseStation](http://woodair.net/SBS/Article/Barebones42_Socket_Data.htm) format, identifying the
closest plane to a specified location. The data of this plane is then saved to a database. When run on a Raspberry Pi,
the data can also be displayed on a connected 128x64 SH1106 LCD screen.

## Prerequisites & Setup

### dump1090

Ensure that [dump1090](https://github.com/flightaware/dump1090) is running and configured to read messages from a
software-controlled radio antenna and broadcast
them in BaseStation format via HTTP. This can be achieved by running dump1090 with the `dump1090 --net` command.
dump1090
can be run on the same device as Planeradar or on a separate device that is accessible from the device running
Planeradar.

The [dump1090.service](setup/dump1090.service) file in this repository can be used to set up a systemctl service for
starting dump1090. Be sure to
adjust the file paths and user in the file as needed.

### Database

Make sure to have a MariaDB or MySQL database available to store the data. The database can either run locally on the
same device as Planeradar or on a separate device that is accessible from Planeradar.
To set up the actual database along with the necessary tables, please refer to
the [database_init.sql](setup/database_init.sql) file in the setup folder.

### Dependencies

Set up a Python environment and use the [requirements.txt](requirements.txt) file to install the necessary requirements.
Note that the requirements.txt file behaves differently depending on whether it is run on Linux or Windows. On Linux, it
installs RPi.GPIO, assuming it runs on an actual Raspberry Pi. Under Windows, Mock.GPIO is used instead, assuming that
the code runs on a development machine.

### Environment Variables

Take the [.env_template](setup/.env_template) file from the setup folder, copy it to the folder that contains
the [planeradar_processor.py](planedata_processor.py) file,
and rename it to `.env`. Then, fill in the values for

- your local position (`LATITUDE` and `LONGITUDE`)
- the database (credentials, address, etc.)
- the address from which to read the dump1090 messages (e.g., `localhost` if run locally)
- the URL of the endpoint at which the planeradar_server receives the data via POST requests (`BROADCAST_SERVER_URL`)

You also need to specify the environment: if it is set to development, Pygame is used to emulate the LCD screen.
Otherwise, the program tries to reach a real LCD screen connected via I2C on the Raspberry Pi's GPIO pins.

### Aircraft Database

Make sure to have the aircraftDatabase.csv file available. To do so, either

1. Run the `planedata_processor.py` with the `-d` or `--download` flag to download the file (this may take some time),
   or
2. Download the file manually from [here](https://opensky-network.org/datasets/metadata/aircraftDatabase.csv) and save
   it next to the `planedata_processor.py` with the name `aircraftDatabase.csv`

This step only needs to be repeated if you want to update to more recent aircraft data.

### Wiring on a RaspberryPi

Connect a 128x64 SH1106 LCD screen via the I2C pins of your Raspberry Pi. Also, connect a red and green status LED, as
well as two switches: one for turning the screen on and off, and the other to decide whether the closest plane or the
closest plane below 15,000 feet shall be displayed on the screen.

You can find out which GPIO pins are used or change the pins by looking at the beginning of
the  [planedata_processor.py](planedata_processor.py) file.

## Running the Planeradar Data Processor

``
python planedata_processor.py -s 4 -b
``

The planeradar data processor reads all incoming messages from dump1090 and analyzes them. It checks for the closest
plane (as well as the closest plane, taking into account a penalty for planes above 15,000 feet), displays it, and saves
it in the database.

It also sends this information to the `BROADCAST_ENDPOINT_URL` of the planeradar_server via a POST request, so that the
server can also display it.

The planeradar data processor can be run with the following options:

| Option               | Description                                                                                                     |
|----------------------|-----------------------------------------------------------------------------------------------------------------|
| `-d`, `--download`   | Flag to indicate that the aircraftDatabase file shall be downloaded before running                              | 
| `-k`, `--keepon`     | Flag to keep the screen on.                                                                                     |
| `-b`, `--broadcast`  | Flag to turn broadcasting information to the planeradar_server on.                                              |
| `-s`, `--screentime` | Set the wait time in seconds between screen refreshes. Can also be set to 0 for immediate refresh (default: 2). |

If you want to run the planeradar data processor automatically using systemctl, you can use
the [planeradar.service](setup/planeradar.service) file. Make sure to adjust file paths and user in the file if
necessary.

## Running the Planeradar Server

``
python planeradar_server.py
``

Runs a server that provides an endpoint to receive plane information from the Planeradar data processor via POST
requests. It publishes the latest information via an HTML site on port 8000, using WebSocket connections for
auto-update.

If you want to run the Planeradar server automatically using systemctl, you can use
the [planeserver.service](setup/planeserver.service) file. Make sure to adjust file paths and user in the file if
necessary.