import os
from pymongo import MongoClient
from slugify import slugify

MONGO_URI = os.getenv("MONGO_URI", "mongodb://root:example@mongodb:27017/jobos?authSource=admin")

def get_db():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return client.get_database("jobos")

def find_or_create_client(email_address: str):
    db = get_db()
    domain = email_address.split('@')[-1].lower()
    
    # Simple logic: map domain to client slug
    # In production, this would be more sophisticated
    client_name = domain.split('.')[0].capitalize()
    slug = slugify(client_name)
    
    client = db.clients.find_one({"slug": slug})
    
    if not client:
        client_data = {
            "name": client_name,
            "slug": slug,
            "domain": domain,
            "status": "active"
        }
        db.clients.insert_one(client_data)
        client = client_data
        print(f"Created new client: {client_name} ({slug})")
    
    return client
