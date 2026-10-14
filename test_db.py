
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

try:
    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

    if connection.is_connected():
        print("MySQL connection successful!")
        print("Connected to database:", connection.database)

    connection.close()

except mysql.connector.Error as error:
    print("MySQL connection failed.")
    print("Error:", error)
