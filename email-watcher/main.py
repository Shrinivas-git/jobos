import time
import os
import imaplib
import email
import httpx
from email.header import decode_header
from datetime import datetime
from utils.client_utils import find_or_create_client, get_db
from utils.jd_utils import generate_jd_id
from utils.storage_utils import create_jd_folder_structure, save_raw_jd_content
from dotenv import load_dotenv

load_dotenv()

print("Email Watcher Service Starting...")
EMAIL_HOST = os.getenv('EMAIL_HOST', 'imap.gmail.com')
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', 300))

print(f"Monitoring Host: {EMAIL_HOST}")
print(f"Monitoring User: {EMAIL_USER}")

def process_email_message(msg):
    """Process an individual email message."""
    sender = email.utils.parseaddr(msg.get("From"))[1]
    subject = msg.get("Subject")
    
    # Decode subject
    decoded_subject = ""
    if subject:
        parts = decode_header(subject)
        for part, encoding in parts:
            if isinstance(part, bytes):
                decoded_subject += part.decode(encoding or "utf-8")
            else:
                decoded_subject += part
    
    print(f"\nProcessing email from: {sender} | Subject: {decoded_subject}")
    
    try:
        # 1. Find or create client
        client = find_or_create_client(sender)
        
        # 2. Check subject for existing JD-ID or generate new one
        import re
        jd_id_match = re.search(r'JD-\d{8}-[a-f0-9]{8}', decoded_subject)
        jd_id = jd_id_match.group(0) if jd_id_match else generate_jd_id()
        
        # 3. Create folder structure
        paths = create_jd_folder_structure(client['slug'], jd_id)
        
        # 4. Extract attachments or body
        has_attachment = False
        body_content = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                if "attachment" in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        file_data = part.get_payload(decode=True)
                        save_raw_jd_content(paths['raw_path'], filename, file_data)
                        print(f"Saved attachment: {filename}")
                        has_attachment = True
                elif content_type == "text/plain" and "attachment" not in content_disposition:
                    body_content = part.get_payload(decode=True).decode()
        else:
            body_content = msg.get_payload(decode=True).decode()
            
        if not has_attachment and body_content:
            save_raw_jd_content(paths['raw_path'], "email_body.txt", body_content.encode('utf-8'))
            print("Saved email body as text file.")
            
        # 5. Store metadata in MongoDB
        db = get_db()
        # Check if JD already exists (e.g. if we're re-processing or updating)
        existing_jd = db.job_descriptions.find_one({"jd_id": jd_id})
        
        jd_data = {
            "client_id": client['_id'],
            "jd_id": jd_id,
            "title": decoded_subject.replace("New JD: ", "").strip(),
            "raw_text": body_content,
            "folder_path": paths['jd_path'],
            "source": "email",
            "sender": sender,
            "status": "received",
            "updated_at": datetime.now()
        }
        
        if not existing_jd:
            jd_data["created_at"] = datetime.now()
            db.job_descriptions.insert_one(jd_data)
        else:
            db.job_descriptions.update_one({"jd_id": jd_id}, {"$set": jd_data})
            
        print(f"JD Ingested Successfully: {jd_id}")

        # 6. Trigger processing via API
        try:
            api_url = os.getenv("API_URL", "http://api:8000")
            httpx.post(f"{api_url}/jd/{jd_id}/process", timeout=10.0)
            print(f"Triggered processing for {jd_id}")
        except Exception as e:
            print(f"[ERROR] Failed to trigger processing: {e}")
    except Exception as e:
        print(f"[ERROR] Failed to process email: {e}")

def poll_mailbox():
    """Connect to IMAP and check for unseen emails."""
    if not EMAIL_USER or not EMAIL_PASSWORD:
        print("[WARN] Email credentials not set. Skipping IMAP poll.")
        return

    try:
        mail = imaplib.IMAP4_SSL(EMAIL_HOST)
        mail.login(EMAIL_USER, EMAIL_PASSWORD)
        mail.select("inbox")
        
        status, messages = mail.search(None, 'UNSEEN')
        if status != 'OK':
            print("[ERROR] Failed to search mailbox")
            return
            
        message_ids = messages[0].split()
        print(f"Found {len(message_ids)} unseen emails.")
        
        for msg_id in message_ids:
            status, data = mail.fetch(msg_id, '(RFC822)')
            if status != 'OK':
                continue
                
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)
            process_email_message(msg)
            
        mail.close()
        mail.logout()
    except Exception as e:
        print(f"[ERROR] IMAP Error: {e}")

def process_mock_email():
    """Simulate receiving an email for Phase 1 testing if real IMAP is not configured."""
    print("\n[MOCK] Running mock email processor...")
    mock_sender = "hr@fidelitus.com"
    mock_subject = "New JD: Senior Backend Engineer"
    mock_body = "We need a Senior Backend Engineer with FastAPI and MongoDB experience."
    
    # Create a simple mock message object-like behavior
    class MockMsg:
        def get(self, key):
            if key == "From": return f"HR <{mock_sender}>"
            if key == "Subject": return mock_subject
            return None
        def is_multipart(self): return False
        def get_payload(self, decode=True): return mock_body.encode('utf-8')
        def walk(self): return []
        
    process_email_message(MockMsg())

# Initial run (Mock for dev safety if no credentials)
if not EMAIL_USER or "@example.com" in EMAIL_USER:
    process_mock_email()

print(f"Entering main loop (polling every {POLL_INTERVAL}s)...")
while True:
    poll_mailbox()
    time.sleep(POLL_INTERVAL)
