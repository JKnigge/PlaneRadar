# Planeradar

This tool can be used to analyse ADS-B messages from [dump1090](https://github.com/flightaware/dump1090). It analyses
the messages incoming in [BaseStation format](http://woodair.net/SBS/Article/Barebones42_Socket_Data.htm), looking for
the closest plane to a given location. It then saves the data of this plane in a database. When being run on a
RaspberryPi, the data can also be displayed on a 128x64 sh1106 LCD screen connected to the device.

## Prerequisites & Setup

### dump1090

Make sure you have [dump1090](https://github.com/flightaware/dump1090) running in such a way that it reads messages via
a software controlled radio antenna and
broadcasts them in BaseStation format via http. To achieve this, run dump1090 via the `dump1090 --net` command. It can
either be run on the same device as Planeradar or on a different device accessible from the device running Planeradar.

The [dump1090.service](setup/dump1090.service) file in this repo can be used to setup a systemctl service to start
dump1090. Make sure to adjust file paths and user in the file if necessary.

### Database

Make sure to have a MariaDB or MySQL database available to store the data. The database can either run locally on the
same device as Planeradar or on a device accessible from Planeradar.

To set up the actual database along with the necessary tables, please refer to
the [database_init.sql](setup/database_init.sql) file in the setup folder.

### Dependencies

Set up a python environment and use the [requirements.txt](requirements.txt) file to install the necessary requirements.
Note that the requirements.txt file behaves differently whether it is run on Linux or a Windows. On Linux, it installs
RPi.GPIO, assuming it runs on an actual RaspberryPi. Under Windows, Mock.GPIO is used instead, assuming that the code
runs in a development machine.

### Environment Variables

Take the [.env_template](setup/.env_template) file from the setup folder, copy it to the folder which contains
the [planeradar_processor.py](planedata_processor.py) file and rename it to `.env`. Then, fill in the values for

- your local position (`LATITUDE` and `LONGITUDE`)
- the database (credentials, address etc.)
- the address from which to read the dump1090 messages (e.g., `localhost` if run locally)
- the url at which the planeradar_server receives the data (`BROADCAST_SERVER_URL`)

You also need to specify the environment: If it is set to `development`, pygame is used to emulate the LCD screen.
Otherwise, the program tries to reach a real LCD screen connected via I2C on the Raspberry's GPIO pins.

### Aircraft Database

Make sure to have the aircraftDatabase.csv file available. To do so, either

1. Run the `planedata_processor.py` with the `-d` or `--download` flag to download the file (may take some time), or
2. Download the file manually from [here](https://opensky-network.org/datasets/metadata/aircraftDatabase.csv) and save
   it next to the `planedata_processor.py` with the name `aircraftDatabase.csv`

This step only needs to be repeated if you want more recent aircraft data.

### Wiring on a RaspberryPi

Connect a 128x64 sh1106 LCD screen via the I2C pins of your Raspberry Pi. Also connect a red and green
status LED as well as two switches, one for turning the screen on and off and the other to decide if the closest plane
or the closest plane below 15,000 feet shall be displayed on the screeen.

You can find out which GPIO pins are used or change the pins by looking at the beginning of
the [planedata_processor.py](planedata_processor.py) file.

## Running the Planeradar Data Processor

``
python planedata_processor.py -s 4 -b
``

The planeradar data processor reads all incoming messages from dump1090 and analyses them. It checks for the closest
plane (as well as the closest plane under consideration of at penalty for planes above 15,000 feet) displays it and
saves it in the database.

It also sends this information to the `BROADCAST_ENDPOINT_URL` of the planeradar_server via a POST request, so that the
server can also display it.

The planeradar data processor can be run with the following options:

| Option               | Description                                                                                                     |
|----------------------|-----------------------------------------------------------------------------------------------------------------|
| `-d`, `--download`   | Flag to indicate that the aircrafDatabase file shall be downloaded before running                               | 
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

Runs a server that provides and endpoint to receive plane information from the Planeradar data processor via POST
requests. It publishes the latest information via a html site on port 8000 using websocket connections for auto-update.

If you want to run the planeradar data processor automatically using systemctl, you can use
the [planeserver.service](setup/planeserver.service) file. Make sure to adjust file paths and user in the file if
necessary.