from utils.client_utils import get_db
db = get_db()
result = db.candidates.update_one({'name': 'Shrinivas Sondur'}, {chr(36) + 'set': {'email': 'srinivassondur03@gmail.com'}})
print('done', result.modified_count)
