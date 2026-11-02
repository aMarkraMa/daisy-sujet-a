import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

#repo backend
PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")

def get_connection():
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)