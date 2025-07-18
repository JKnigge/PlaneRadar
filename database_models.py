from peewee import Model, CharField, FloatField
from database_utils import database
from peewee import IntegerField, DateTimeField


class BaseModel(Model):
    class Meta:
        database = database


class Callsigns(BaseModel):
    id = IntegerField(primary_key=True)
    hex_ident = CharField(null=True)
    callsign = CharField()
    first_message_generated = DateTimeField(null=True)
    first_message_received = DateTimeField()
    last_message_generated = DateTimeField(null=True)
    last_message_received = DateTimeField()
    registration = CharField(null=True)
    typecode = CharField(null=True)
    operator = CharField(null=True)
    num_messages = IntegerField()
    closest_dist = FloatField(null=True)
    lowest_alt = IntegerField(null = True)


class Positions(BaseModel):
    id = IntegerField(primary_key=True)
    hex_ident = CharField(null=True)
    callsign_id = IntegerField()
    latitude = FloatField(null=True)
    longitude = FloatField(null=True)
    altitude = IntegerField(null=True)
    distance = FloatField(null=True)
    bearing = FloatField(null=True)
    message_generated = DateTimeField(null=True)
    message_received = DateTimeField()
    num_message = IntegerField()


