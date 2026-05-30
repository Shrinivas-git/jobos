import uuid
import logging
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import smtplib
import os

from celery_app import celery
from utils.client_utils import get_db
from utils.invoice_utils import generate_invoice_pdf, save_invoice_pdf
from utils.email_utils import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM

logger = logging.getLogger(__name__)


def _parse_compensation_range(comp_range: str) -> float:
    """Extract numeric value from compensation_range string (e.g., '100000-120000' -> 110000)."""
    try:
        if not comp_range:
            return 0.0
        parts = comp_range.split('-')
        if len(parts) >= 2:
            low = float(parts[0].replace(',', '').strip())
            high = float(parts[1].replace(',', '').strip())
            return (low + high) / 2
        else:
            return float(parts[0].replace(',', '').strip())
    except Exception as e:
        logger.error(f"Failed to parse compensation_range '{comp_range}': {e}")
        return 0.0


def _send_invoice_email(to_address: str, invoice_id: str, pdf_path: str) -> bool:
    """Send invoice PDF via email with attachment."""
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured — skipping invoice email")
        return False

    try:
        msg = MIMEMultipart()
        msg["Subject"] = f"Invoice {invoice_id} - Placement Fee"
        msg["From"] = SMTP_FROM
        msg["To"] = to_address

        body_html = f"""<!DOCTYPE html>
<html><body style="font-family:-apple-system,sans-serif;background:#0f172a;color:#f1f5f9;padding:24px">
  <div style="max-width:640px;margin:0 auto;background:#1e293b;padding:24px;border-radius:12px">
    <h2 style="color:#f1f5f9;margin:0 0 12px 0">Placement Invoice</h2>
    <p style="color:#cbd5e1">Your invoice for the recent placement is attached.</p>
    <p style="color:#cbd5e1">Invoice ID: <b>{invoice_id}</b></p>
    <p style="color:#94a3b8;font-size:12px;margin-top:24px">JobOS · Closure Engine</p>
  </div>
</body></html>"""

        msg.attach(MIMEText(body_html, "html"))

        with open(pdf_path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename= {os.path.basename(pdf_path)}",
            )
            msg.attach(part)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, to_address, msg.as_string())

        logger.info(f"Invoice email sent to {to_address}: {invoice_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to send invoice email to {to_address}: {e}")
        return False


@celery.task(name="tasks.invoice_tasks.generate_and_send_invoice")
def generate_and_send_invoice(jd_id: str, candidate_id: str):
    """Generate invoice, save to MongoDB and disk, send to client."""
    db = get_db()
    invoice_id = str(uuid.uuid4())

    jd = db.job_descriptions.find_one(
        {"jd_id": jd_id},
        {"structured_data": 1, "title": 1, "client_email": 1}
    )
    if not jd:
        logger.error(f"JD {jd_id} not found for invoice generation")
        return {"ok": False, "error": "JD not found"}

    candidate = db.candidates.find_one(
        {"candidate_id": candidate_id},
        {"name": 1}
    )
    if not candidate:
        logger.error(f"Candidate {candidate_id} not found for invoice generation")
        return {"ok": False, "error": "Candidate not found"}

    pipeline = db.pipeline_stages.find_one(
        {"jd_id": jd_id, "candidate_id": candidate_id},
        {"stages": 1}
    )
    if not pipeline:
        logger.error(f"Pipeline not found for {jd_id} / {candidate_id}")
        return {"ok": False, "error": "Pipeline not found"}

    structured = jd.get("structured_data") or {}
    jd_title = structured.get("title") or jd.get("title") or jd_id
    client_email = jd.get("client_email") or structured.get("client_email") or ""
    compensation_range = structured.get("compensation_range") or ""

    candidate_name = candidate.get("name") or candidate_id
    placement_date = datetime.utcnow()

    if not client_email:
        logger.error(f"No client_email found for JD {jd_id}")
        return {"ok": False, "error": "Client email missing"}

    avg_compensation = _parse_compensation_range(compensation_range)
    fee_amount = avg_compensation * 0.15

    try:
        pdf_bytes = generate_invoice_pdf(
            invoice_id=invoice_id,
            candidate_name=candidate_name,
            jd_title=jd_title,
            client_email=client_email,
            placement_date=placement_date,
            fee_amount=fee_amount,
        )

        pdf_path = save_invoice_pdf(jd_id, candidate_id, pdf_bytes)

        db.invoices.insert_one({
            "invoice_id": invoice_id,
            "jd_id": jd_id,
            "candidate_id": candidate_id,
            "candidate_name": candidate_name,
            "jd_title": jd_title,
            "client_email": client_email,
            "amount": fee_amount,
            "compensation_range": compensation_range,
            "placement_date": placement_date,
            "pdf_path": pdf_path,
            "generated_at": datetime.utcnow(),
            "sent_at": None,
            "email_status": "pending",
            "payment_status": "unpaid",
            "paid_at": None,
        })

        # Recipients: client + all managers (deduped)
        manager_emails = [
            u["email"] for u in db.users.find({"roles": {"$in": ["manager"]}}, {"email": 1})
            if u.get("email")
        ]
        recipients = list(dict.fromkeys([client_email] + manager_emails))
        email_sent = False
        for addr in recipients:
            if _send_invoice_email(addr, invoice_id, pdf_path):
                email_sent = True

        if email_sent:
            db.invoices.update_one(
                {"invoice_id": invoice_id},
                {
                    "$set": {
                        "email_status": "sent",
                        "sent_at": datetime.utcnow(),
                    }
                },
            )
            logger.info(f"Invoice {invoice_id} generated, saved, and emailed successfully")
            return {"ok": True, "invoice_id": invoice_id}
        else:
            db.invoices.update_one(
                {"invoice_id": invoice_id},
                {"$set": {"email_status": "failed"}},
            )
            logger.warning(f"Invoice {invoice_id} generated and saved, but email send failed")
            return {"ok": True, "invoice_id": invoice_id, "email_sent": False}

    except Exception as e:
        logger.error(f"Failed to generate invoice for {jd_id}/{candidate_id}: {e}")
        return {"ok": False, "error": str(e)}


@celery.task(name="tasks.invoice_tasks.check_overdue_invoices")
def check_overdue_invoices():
    """Daily task: find unpaid invoices older than 30 days and email recruiter + manager."""
    from utils.email_utils import send_email
    db = get_db()
    cutoff = datetime.utcnow() - timedelta(days=30)

    overdue = list(db.invoices.find({
        "payment_status": {"$in": ["unpaid", None]},
        "sent_at": {"$lte": cutoff},
        "email_status": "sent",
    }, {"_id": 0}))

    if not overdue:
        logger.info("No overdue invoices found")
        return {"checked": 0}

    # Get manager/recruiter emails from users collection
    staff = list(db.users.find(
        {"role": {"$in": ["manager", "recruiter"]}},
        {"email": 1, "_id": 0}
    ))
    staff_emails = [u["email"] for u in staff if u.get("email")]

    for inv in overdue:
        days_overdue = (datetime.utcnow() - inv["sent_at"]).days
        subject = f"Payment Overdue — Invoice {inv['invoice_id'][:8].upper()} ({days_overdue} days)"
        body = f"""<!DOCTYPE html>
<html><body style="font-family:-apple-system,sans-serif;background:#0f172a;color:#f1f5f9;padding:24px">
  <div style="max-width:600px;margin:0 auto;background:#1e293b;padding:24px;border-radius:12px;border:1px solid #ef4444">
    <h2 style="color:#ef4444;margin:0 0 12px 0">⚠ Invoice Payment Overdue</h2>
    <p style="color:#cbd5e1">The following invoice has not been paid for <b>{days_overdue} days</b>.</p>
    <table style="width:100%;border-collapse:collapse;margin:16px 0">
      <tr><td style="color:#94a3b8;padding:6px 0">Invoice ID</td><td style="color:#f1f5f9">{inv['invoice_id']}</td></tr>
      <tr><td style="color:#94a3b8;padding:6px 0">Client</td><td style="color:#f1f5f9">{inv.get('client_email','—')}</td></tr>
      <tr><td style="color:#94a3b8;padding:6px 0">Candidate</td><td style="color:#f1f5f9">{inv.get('candidate_name','—')}</td></tr>
      <tr><td style="color:#94a3b8;padding:6px 0">Role</td><td style="color:#f1f5f9">{inv.get('jd_title','—')}</td></tr>
      <tr><td style="color:#94a3b8;padding:6px 0">Amount</td><td style="color:#f1f5f9">₹{inv.get('amount',0):,.0f}</td></tr>
      <tr><td style="color:#94a3b8;padding:6px 0">Invoice Sent</td><td style="color:#f1f5f9">{inv['sent_at'].strftime('%d %b %Y')}</td></tr>
    </table>
    <p style="color:#94a3b8;font-size:12px">Please follow up with the client immediately.</p>
    <p style="color:#94a3b8;font-size:11px;margin-top:24px">JobOS · Finance Alerts</p>
  </div>
</body></html>"""

        for email in staff_emails:
            send_email(to=email, subject=subject, html_body=body)
            logger.info(f"Overdue reminder sent to {email} for invoice {inv['invoice_id']}")

    logger.info(f"Overdue check complete: {len(overdue)} invoices flagged")
    return {"checked": len(overdue)}
