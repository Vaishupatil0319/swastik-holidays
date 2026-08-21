import pymysql

def get_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="Student",
        database="swastik_holidays",
        cursorclass=pymysql.cursors.DictCursor
    )