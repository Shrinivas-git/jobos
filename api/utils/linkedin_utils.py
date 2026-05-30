import os

FRONTEND_URL = os.getenv("FRONTEND_URL", os.getenv("APP_BASE_URL", "http://localhost:5173"))


def _as_text(value) -> str:
    """Normalize a field that may be a string or a list of bullet points into text."""
    if isinstance(value, list):
        return ". ".join(str(v).strip().rstrip(".") for v in value if str(v).strip())
    return str(value or "")


def generate_linkedin_post_draft(jd: dict) -> str:
    title = jd.get("title", "")
    structured = jd.get("structured_data") or {}
    jd_id = jd.get("jd_id", "")

    location = structured.get("location") or jd.get("location", "")
    work_structure = structured.get("work_structure", "")
    skills = structured.get("skills") or []
    relevant_exp = structured.get("relevant_experience", "")
    responsibilities = _as_text(structured.get("responsibilities", ""))
    role_type = structured.get("role_type", "")

    apply_url = f"{FRONTEND_URL}/apply/{jd_id}?source=linkedin"

    lines = [f"We're Hiring: {title}"]
    if location:
        lines[0] += f" | {location}"
    lines.append("")

    if responsibilities:
        sentences = responsibilities.strip().split(". ")
        short_desc = ". ".join(sentences[:2]).strip()
        if short_desc and not short_desc.endswith("."):
            short_desc += "."
        lines.append(short_desc)
        lines.append("")

    lines.append("What we're looking for:")
    for skill in skills[:6]:
        lines.append(f"- {skill}")
    if relevant_exp:
        lines.append(f"- {relevant_exp}+ years of relevant experience")
    if work_structure:
        lines.append(f"- Work mode: {work_structure}")

    lines.append("")
    if location:
        lines.append(f"Location: {location}")
    if role_type and role_type not in ("Any", ""):
        lines.append(f"Type: {role_type}")

    lines.append("")
    lines.append(f"Interested? Apply here: {apply_url}")
    lines.append("")

    hashtags = ["#hiring", "#jobs"]
    if title:
        hashtags.append("#" + "".join(w.capitalize() for w in title.split()[:2]))
    if location:
        loc = location.split(",")[0].strip().replace(" ", "")
        if loc:
            hashtags.append(f"#{loc}")
    lines.append(" ".join(hashtags))

    return "\n".join(lines)


def generate_linkedin_job_listing(jd: dict) -> str:
    """Content formatted for LinkedIn's 'Post a Job' form fields (Option B)."""
    title = jd.get("title", "")
    structured = jd.get("structured_data") or {}
    jd_id = jd.get("jd_id", "")

    location = structured.get("location") or jd.get("location", "")
    work_structure = (structured.get("work_structure", "") or "").lower()
    skills = structured.get("skills") or []
    relevant_exp = structured.get("relevant_experience", "")
    responsibilities = _as_text(structured.get("responsibilities", ""))

    if "remote" in work_structure:
        workplace = "Remote"
    elif "hybrid" in work_structure:
        workplace = "Hybrid"
    else:
        workplace = "On-site"

    apply_url = f"{FRONTEND_URL}/apply/{jd_id}?source=linkedin"

    desc_lines = []
    if responsibilities:
        desc_lines.append(responsibilities.strip())
        desc_lines.append("")
    if skills:
        desc_lines.append("Required skills: " + ", ".join(skills))
    if relevant_exp:
        desc_lines.append(f"Experience: {relevant_exp}+ years")
    desc_lines.append("")
    desc_lines.append(f"To apply, please use this link: {apply_url}")
    description = "\n".join(desc_lines)

    lines = [
        f"Job title: {title}",
        "Company: Refining Skills",
        f"Workplace type: {workplace}",
        f"Job location: {location}",
        "Job type: Full-time",
        f"External apply link: {apply_url}",
        "",
        "Description:",
        description,
    ]
    return "\n".join(lines)


def linkedin_draft_email_html(jd: dict, draft: str) -> str:
    title = jd.get("title", "")
    jd_id = jd.get("jd_id", "")

    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    post_escaped = esc(draft)
    listing_escaped = esc(generate_linkedin_job_listing(jd))

    box = ("background:#f3f4f6;border-left:4px solid #0a66c2;padding:16px;margin:8px 0 16px;"
           "white-space:pre-wrap;font-family:monospace;font-size:13px")

    return f"""
    <div style="font-family:sans-serif;max-width:640px;margin:0 auto;padding:24px">
      <h2 style="color:#0a66c2">LinkedIn — {title}</h2>
      <p>Your job <strong>{title}</strong> (JD: {jd_id}) is ready for LinkedIn.
      You have two options below — use whichever you prefer.</p>

      <h3 style="margin-top:24px">Option A — Quick Post (free, fast)</h3>
      <p style="color:#6b7280;font-size:13px;margin:4px 0">Paste this as a normal LinkedIn post on your feed.</p>
      <div style="{box}">{post_escaped}</div>

      <h3 style="margin-top:24px">Option B — Job Listing (gives a Job ID)</h3>
      <p style="color:#6b7280;font-size:13px;margin:4px 0">Use LinkedIn's "Post a Job" and fill these fields.
      This gives a Job ID so JobOS can auto-pull applicants.</p>
      <div style="{box}">{listing_escaped}</div>

      <p style="color:#6b7280;font-size:13px;margin-top:20px">
        <strong>If you use Option B:</strong> after posting, copy the Job ID from the URL
        (e.g. linkedin.com/jobs/view/<strong>4227631788</strong>) and paste it into JobOS
        on the JD page to activate automatic applicant polling.
      </p>
    </div>
    """
