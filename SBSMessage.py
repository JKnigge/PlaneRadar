from datetime import datetime


class SBSMessage:
    def __init__(self, raw_message, aircraft_data):
        fields = raw_message.split(",")
        try:
            self.message_type = fields[0]
            self.transmission_type = fields[1]
            self.session_id = fields[2]
            self.aircraft_id = fields[3]
            self.hex_ident = fields[4]
            self.flight_id = fields[5]
            self.date_generated = fields[6]
            self.time_generated = fields[7]
            self.date_logged = fields[8]
            self.time_logged = fields[9]
            self.callsign = fields[10]
            self.altitude = fields[11]
            self.ground_speed = fields[12]
            self.track = fields[13]
            self.latitude = fields[14]
            self.longitude = fields[15]
            self.vertical_rate = fields[16]
            self.squawk = fields[17]
            self.alert = fields[18]
            self.emergency = fields[19]
            self.spi = fields[20]
            self.is_on_ground = fields[21]
            self.registration = ""
            self.typecode = ""
            self.operator = ""
            self.get_aircraft_information(aircraft_data)
        except IndexError:
            pass

    def get_aircraft_information(self, aircraft_data):
        if self.hex_ident is not None:
            try:
                record = aircraft_data[self.hex_ident.lower()]
                self.registration = record["registration"]
                self.typecode = record["typecode"]
                self.operator = record["operator"]
            except KeyError:
                pass

    def get_generated_datetime(self):
        date_time_str = f"{self.date_generated} {self.time_generated}"
        return datetime.strptime(date_time_str, "%Y/%m/%d %H:%M:%S.%f")