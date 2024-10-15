import os
from functools import wraps

from dotenv import load_dotenv
from peewee import *

load_dotenv()

database = MySQLDatabase(
    os.getenv("DATABASE_NAME"),
    user=os.getenv("DATABASE_USER"),
    password=os.getenv("DATABASE_PW"),
    host=os.getenv("DATABASE_HOST"),
    port=int(os.getenv("DATABASE_PORT")))


def use_db_connection(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        if database.is_closed():
            database.connect()
        try:
            result = f(*args, **kwargs)
            if not database.is_closed():
                database.close()
            return result
        except Exception as e:
            if not database.is_closed():
                database.close()
            raise

    return decorator