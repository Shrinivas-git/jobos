import os
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://root:example@mongodb:27017/jobos?authSource=admin")

def fix_indexes():
    client = MongoClient(MONGO_URI)
    db = client.get_database("jobos")
    
    collections_to_fix = ["candidate_pools", "pipeline_stages"]
    
    for coll_name in collections_to_fix:
        print(f"Fixing indexes for {coll_name}...")
        coll = db[coll_name]
        
        # Drop all indexes except _id
        try:
            coll.drop_indexes()
            print(f" - Dropped all indexes for {coll_name}")
        except Exception as e:
            print(f" - Error dropping indexes for {coll_name}: {e}")
            
        # Recreate correct compound unique index
        try:
            coll.create_index([("jd_id", 1), ("candidate_id", 1)], unique=True)
            print(f" - Created compound unique index (jd_id, candidate_id) for {coll_name}")
        except Exception as e:
            print(f" - Error creating compound index for {coll_name}: {e}")

if __name__ == "__main__":
    fix_indexes()
