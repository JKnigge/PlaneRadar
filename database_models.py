from peewee import Model, CharField
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


