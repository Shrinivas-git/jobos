import os
import logging
from utils.email_utils import send_email

logger = logging.getLogger(__name__)

RECRUITER_EMAIL = os.getenv("RECRUITER_EMAIL", "radhika@refiningskills.org")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:5173")
COMPANY_NAME = os.getenv("COMPANY_NAME", "Refining Skills")

PORTAL_INSTRUCTIONS = {
    "internshala": {
        "name": "Internshala",
        "post_url": "https://internshala.com/recruiter/post-job",
        "steps": [
            "Go to internshala.com and log in",
            "Click 'Post a Job'",
            "Fill in the job title, description, skills, location",
            "In the Apply URL field paste the apply link below",
            "Submit the job",
        ]
    },
    "shine": {
        "name": "Shine.com",
        "post_url": "https://www.shine.com/recruiter/job-posting",
        "steps": [
            "Go to shine.com and log in as recruiter",
            "Click 'Post a Job'",
            "Fill in the job details",
            "Set the Apply URL to the link below",
            "Submit",
        ]
    },
    "workindia": {
        "name": "WorkIndia",
        "post_url": "https://employer.workindia.in/post-job",
        "steps": [
            "Go to employer.workindia.in and log in",
            "Click 'Post a Job'",
            "Fill in job title, description, location, salary",
            "Paste the apply link below in the external apply URL field",
            "Submit",
        ]
    },
    "glassdoor": {
        "name": "Glassdoor",
        "post_url": "https://www.glassdoor.co.in/employers/post-a-job",
        "steps": [
            "Go to glassdoor.co.in and log in as employer",
            "Click 'Post a Job'",
            "Fill in the job details",
            "Set external apply URL to the link below",
            "Submit",
        ]
    },
    "placementindia": {
        "name": "PlacementIndia",
        "post_url": "https://www.placementindia.com/recruiter/post-job.asp",
        "steps": [
            "Go to placementindia.com and log in",
            "Click 'Post a Job'",
            "Fill in job details",
            "Paste the apply link below in the apply URL field",
            "Submit",
        ]
    },
}


def send_portal_failure_email(jd_id: str, job_title: str, portal: str, error: str, structured: dict = None):
    info = PORTAL_INSTRUCTIONS.get(portal, {
        "name": portal.title(),
        "post_url": "#",
        "steps": ["Log in to the portal and post the job manually"]
    })

    apply_url = f"{APP_BASE_URL}/apply/{jd_id}?source={portal}"
    structured = structured or {}

    location = structured.get("location", "")
    salary = structured.get("compensation_range", "")
    experience = f"{structured.get('relevant_experience', '')}-{structured.get('total_experience', '')} years" if structured.get("relevant_experience") else ""
    skills = ", ".join(structured.get("skills", [])[:8]) if structured.get("skills") else ""
    responsibilities = structured.get("responsibilities", "")[:500] if structured.get("responsibilities") else ""

    steps_html = "".join(f"<li style='margin:6px 0;color:#374151'>{s}</li>" for s in info["steps"])

    html = f"""
    <div style="font-family:sans-serif;max-width:640px;margin:0 auto;padding:24px;background:#f9fafb">
      <div style="background:#fff;border-radius:12px;padding:24px;border:1px solid #e5e7eb">

        <h2 style="color:#dc2626;margin:0 0 4px 0">Action Required — Post Job Manually</h2>
        <p style="color:#6b7280;margin:0 0 20px 0">Auto-posting to <strong>{info["name"]}</strong> failed. Please post this job manually.</p>

        <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:12px;margin-bottom:20px">
          <strong style="color:#dc2626">Error:</strong> <span style="color:#7f1d1d;font-size:13px">{error}</span>
        </div>

        <h3 style="color:#111827;margin:0 0 12px 0">Job Details</h3>
        <table style="width:100%;border-collapse:collapse;margin-bottom:20px">
          <tr><td style="padding:8px;color:#6b7280;width:130px">Title</td><td style="padding:8px;font-weight:600">{job_title}</td></tr>
          <tr style="background:#f9fafb"><td style="padding:8px;color:#6b7280">Job ID</td><td style="padding:8px">{jd_id}</td></tr>
          {"<tr><td style='padding:8px;color:#6b7280'>Location</td><td style='padding:8px'>" + location + "</td></tr>" if location else ""}
          {"<tr style='background:#f9fafb'><td style='padding:8px;color:#6b7280'>Salary</td><td style='padding:8px'>" + salary + "</td></tr>" if salary else ""}
          {"<tr><td style='padding:8px;color:#6b7280'>Experience</td><td style='padding:8px'>" + experience + "</td></tr>" if experience else ""}
          {"<tr style='background:#f9fafb'><td style='padding:8px;color:#6b7280'>Skills</td><td style='padding:8px'>" + skills + "</td></tr>" if skills else ""}
        </table>

        {"<h3 style='color:#111827;margin:0 0 8px 0'>Job Description</h3><p style='color:#374151;font-size:14px;line-height:1.6'>" + responsibilities + "...</p>" if responsibilities else ""}

        <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:16px;margin:20px 0">
          <strong style="color:#1d4ed8">Apply Link (paste this in the portal):</strong><br>
          <a href="{apply_url}" style="color:#2563eb;word-break:break-all;font-size:13px">{apply_url}</a>
        </div>

        <h3 style="color:#111827;margin:0 0 12px 0">Steps to Post on {info["name"]}</h3>
        <ol style="margin:0 0 20px 0;padding-left:20px">{steps_html}</ol>

        <a href="{info["post_url"]}" style="display:inline-block;background:#2563eb;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600">
          Open {info["name"]} → Post a Job
        </a>

      </div>
      <p style="color:#9ca3af;font-size:12px;text-align:center;margin-top:16px">Sent by JobOS — {COMPANY_NAME}</p>
    </div>
    """

    subject = f"[Post Now] {job_title} on {info['name']} | {jd_id}"
    sent = send_email(RECRUITER_EMAIL, subject, html)
    if sent:
        logger.info(f"[Email Publisher] Failure email sent for {jd_id} on {portal}")
    else:
        logger.error(f"[Email Publisher] Failed to send failure email for {jd_id} on {portal}")
