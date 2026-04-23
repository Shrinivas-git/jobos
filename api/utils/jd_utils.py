import uuid
from datetime import datetime

def generate_jd_id():
    date_str = datetime.now().strftime("%Y%m%d")
    short_uuid = str(uuid.uuid4())[:8]
    return f"JD-{date_str}-{short_uuid}"
