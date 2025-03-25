import requests
import psycopg2
from psycopg2 import sql
from config.constants import DB_CONFIG

def get_db_connection(**dbconfig):
    return psycopg2.connect(
        dbname=dbconfig["dbname"],
        user=dbconfig["user"],
        password=dbconfig["password"],
        host=dbconfig["host"]
    )