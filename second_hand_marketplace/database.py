"""
database.py - MySQL helper functions for ReMarket.

Every query in the project goes through these helpers, and every helper
uses PARAMETERISED SQL (the %s placeholders). User input is never pasted
into a SQL string, which protects the application from SQL injection.

Connection settings can be changed with environment variables:
    DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
"""
import os

import mysql.connector
from mysql.connector import Error, IntegrityError  # noqa: F401  (re-exported for app.py)

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "3306")),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "second_hand_marketplace"),
    "charset": "utf8mb4",
    "autocommit": True,
}


def get_connection():
    """Open a new connection to the MySQL database."""
    return mysql.connector.connect(**DB_CONFIG)


def query_all(sql, params=None):
    """Run a SELECT and return all rows as a list of dictionaries."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        cursor.close()
        return rows
    finally:
        conn.close()


def query_one(sql, params=None):
    """Run a SELECT and return the first row (or None)."""
    rows = query_all(sql, params)
    return rows[0] if rows else None


def execute(sql, params=None):
    """Run an INSERT / UPDATE / DELETE. Returns the number of affected rows."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        affected = cursor.rowcount
        cursor.close()
        return affected
    finally:
        conn.close()


def insert(sql, params=None):
    """Run an INSERT and return the new AUTO_INCREMENT id."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        new_id = cursor.lastrowid
        cursor.close()
        return new_id
    finally:
        conn.close()
