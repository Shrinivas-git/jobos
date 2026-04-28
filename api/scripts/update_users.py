import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.client_utils import get_db
from datetime import datetime

db = get_db()
db.users.delete_many({})
db.users.insert_many([
    {"email": "sca24mca0114@dsu.edu.in", "username": "manager", "roles": ["manager"], "last_seen": datetime.utcnow()},
    {"email": "sca24mca0114@dsu.edu.in", "username": "hod", "roles": ["hod"], "last_seen": datetime.utcnow()},
])
print("Done")
