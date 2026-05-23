from utils.client_utils import get_db

db = get_db()
count = db.candidates.count_documents({"source": "unipile_linkedin"})
candidates = list(db.candidates.find({"source": "unipile_linkedin"}, {"name": 1, "headline": 1, "location": 1, "created_at": 1}))
print(f"Total LinkedIn profiles fetched: {count}")
for c in candidates:
    print(f"  - {c.get('name')} | {c.get('headline','')[:50]} | {c.get('location','')}")
