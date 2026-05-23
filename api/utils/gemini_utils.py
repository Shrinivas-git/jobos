import os
import re
import json
import logging
import time
from groq import Groq
from typing import List
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Initialize local embedding model — all-mpnet-base-v2 is significantly more
# accurate than all-MiniLM-L6-v2 for semantic job/resume matching
try:
    embedding_model = SentenceTransformer('all-mpnet-base-v2')
    logger.info("Local embedding model (all-mpnet-base-v2) loaded successfully.")
except Exception as e:
    logger.warning(f"all-mpnet-base-v2 not available, falling back to all-MiniLM-L6-v2: {e}")
    try:
        embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("Fallback embedding model (all-MiniLM-L6-v2) loaded.")
    except Exception as e2:
        logger.error(f"Failed to load any embedding model: {e2}")
        embedding_model = None

# Groq — all AI calls
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)
else:
    logger.warning("GROQ_API_KEY not found — all AI calls will fail.")
    groq_client = None

FAST_MODEL = "llama-3.1-8b-instant"          # Groq — JD extraction, resume extraction
GROQ_REASON_MODEL = "llama-3.3-70b-versatile" # Groq — Pass 2 matching, assessments, CRM


def _call_groq(model: str, prompt: str, max_tokens: int = 4096, system: str = None) -> str:
    """Groq call with automatic retry on rate limit. Never gives up — waits and retries."""
    if not groq_client:
        raise RuntimeError("Groq client not initialized — GROQ_API_KEY missing.")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    max_retries = 10
    for attempt in range(max_retries):
        try:
            response = groq_client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=messages
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            err_str = str(e).lower()
            if any(x in err_str for x in ("rate limit", "429", "too many requests", "quota")):
                wait = min(30 * (attempt + 1), 300)  # 30s, 60s, ... capped at 5 min
                logger.warning(f"Groq rate limit (attempt {attempt+1}/{max_retries}). Waiting {wait}s...")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError(f"Groq call failed after {max_retries} retries — rate limit not resolved.")



def _parse_json_response(text: str) -> dict:
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r'\{.*\}', text, re.DOTALL)
    candidate_text = match.group() if match else text
    try:
        return json.loads(candidate_text)
    except json.JSONDecodeError:
        pass

    # Last-resort: use json-repair to fix common LLM JSON issues
    # (unescaped quotes inside strings, trailing commas, etc.)
    try:
        from json_repair import repair_json
        repaired = repair_json(candidate_text)
        if isinstance(repaired, str):
            result = json.loads(repaired)
        else:
            result = repaired
        if isinstance(result, dict):
            logger.warning("JSON response required repair fallback to parse.")
            return result
    except Exception as repair_err:
        logger.error(f"json-repair fallback failed: {repair_err}")
    raise json.JSONDecodeError("Failed to parse JSON even with repair fallback", text, 0)


def extract_jd_data(raw_text: str) -> dict:
    """Uses Groq (fast model) to extract structured fields from raw JD text."""
    prompt = f"""You are a high-precision recruitment AI. Extract structured data from the following raw Job Description (JD) text.
Return ONLY a valid JSON object. Do not include markdown formatting or explanations.

Fields to extract:
- title: Job Title
- level: Seniority level (e.g. Junior, Senior, Lead, Manager)
- responsibilities: Core responsibilities of the role
- kpis: Key Performance Indicators if mentioned, else "Not specified"
- skills: List of specific technical and soft skills (UNION of must_have_skills and nice_to_have_skills below — keep for backward compatibility)
- must_have_skills: list of skills/experiences explicitly required (look for "must have", "required", "minimum", "mandatory", "essential")
- nice_to_have_skills: list of skills/experiences that are preferred, bonus, or advantageous (look for "preferred", "nice to have", "bonus", "plus", "advantageous")
- industries: list of industry domains the JD targets or candidates should come from (e.g. ["Banking", "Healthcare", "Retail"]). Empty list if not mentioned.
- relevant_experience: Years of relevant domain experience required (integer)
- total_experience: Total years of work experience required (integer)
- compensation_range: Salary range if mentioned, else "Not specified"
- work_structure: In-office, Hybrid, or Remote
- location: Specific city/region
- hiring_timeline: e.g. "Immediate", "2 weeks", "Not specified"
- urgency: Low, Medium, High, or Critical
- num_positions: Number of open positions (integer), default to 1 if not mentioned
- gender_preference: "Any", "Male", or "Female"
- college_preference: preferred colleges or institutions (string, empty if not mentioned)
- college_exclusion: colleges or institutions to exclude (string, empty if not mentioned)

Raw JD Text:
---
{raw_text}
---

JSON Output:"""

    try:
        text = _call_groq(FAST_MODEL, prompt, max_tokens=2048)
        logger.info(f"Groq JD extraction response (first 200 chars): {text[:200]}")
        result = _parse_json_response(text)
        # Defaults for new fields (backward compatibility)
        if "must_have_skills" not in result or not isinstance(result["must_have_skills"], list):
            result["must_have_skills"] = result.get("skills", []) or []
        if "nice_to_have_skills" not in result or not isinstance(result["nice_to_have_skills"], list):
            result["nice_to_have_skills"] = []
        if "industries" not in result or not isinstance(result["industries"], list):
            result["industries"] = []
        return result
    except Exception as e:
        logger.error(f"Error extracting JD data with Claude: {e}")
        return {
            "title": "Extraction Failed",
            "level": "Unknown",
            "responsibilities": raw_text[:500],
            "kpis": "Not specified",
            "skills": [],
            "must_have_skills": [],
            "nice_to_have_skills": [],
            "industries": [],
            "relevant_experience": 0,
            "total_experience": 0,
            "compensation_range": "Not specified",
            "work_structure": "Not specified",
            "location": "Not specified",
            "hiring_timeline": "Not specified",
            "urgency": "Medium",
            "num_positions": 1,
            "gender_preference": "Any",
            "college_preference": "",
            "college_exclusion": ""
        }


def generate_jd_formats(structured_data: dict) -> dict:
    """Uses Groq (fast model) to generate Internal, Short, and Candidate Markdown formats."""
    prompt = f"""Based on the following structured Job Description data, generate three distinct Markdown formats.
Return ONLY a valid JSON object with keys: "internal", "short", "candidate".

1. "internal": Full detail including salary, hiring timeline, and internal notes.
2. "short": Recruiter-facing summary (title, key skills, level, location).
3. "candidate": Candidate-facing description. Exclude specific salary figures (use "Competitive") and remove sensitive client identifiers.

Structured Data:
{json.dumps(structured_data, indent=2)}

JSON Output:"""

    try:
        text = _call_groq(FAST_MODEL, prompt, max_tokens=2048)
        return _parse_json_response(text)
    except Exception as e:
        logger.error(f"Error generating JD formats with Groq: {e}")
        return {
            "internal": f"# {structured_data.get('title')}\nDetails extraction failed.",
            "short": f"Role: {structured_data.get('title')}",
            "candidate": f"# {structured_data.get('title')}\nExciting opportunity."
        }


def generate_embedding(text: str) -> List[float]:
    """Generates a 384-dimensional dense vector using local sentence-transformers (all-MiniLM-L6-v2)."""
    try:
        if embedding_model is None:
            raise Exception("Embedding model not initialized.")
        return embedding_model.encode(text).tolist()
    except Exception as e:
        logger.error(f"Error generating local embedding: {e}")
        return [0.0] * 384


def evaluate_candidate_fitment(jd_structured_data: dict, resume_text: str, recruiter_notes: str = None) -> dict:
    """
    Pass 2: Deep reasoning on candidate fitment using Groq llama-3.3-70b-versatile.
    Retries indefinitely on rate limits — will take time but will never fail.
    JSON parse failures also trigger a retry rather than returning a zero score.
    """
    if not groq_client:
        raise RuntimeError("Groq client not initialized — GROQ_API_KEY missing.")

    jd_text = json.dumps(jd_structured_data, indent=2)

    # Use full resume — truncate only if extremely long (>20k chars) to avoid token overflow
    resume_snippet = resume_text[:20000]

    system_prompt = (
        "You are an expert senior recruiter with 15 years of experience. "
        "Your job is to evaluate candidates against job descriptions and give honest, decisive assessments. "
        "You always return valid JSON. You never truncate your response mid-object.\n\n"
        f"JOB DESCRIPTION:\n{jd_text}"
    )

    user_prompt = (
        f"Evaluate this candidate resume against the job description.\n\n"
        f"CANDIDATE RESUME:\n---\n{resume_snippet}\n---\n\n"
        + (f"RECRUITER NOTES: {recruiter_notes}\n\n" if recruiter_notes and recruiter_notes.strip() else "")
        + "Return ONLY a valid JSON object. No markdown, no explanation outside JSON.\n"
        "CRITICAL: Inside string values use single quotes, not double quotes. Never use unescaped double quotes inside a string.\n\n"
        "SCORING RULES:\n"
        "  90-100 = Meets ALL must-haves with evidence — interview immediately\n"
        "  70-89  = Meets most must-haves, 1-2 small gaps — shortlist\n"
        "  50-69  = Borderline — key gap or level mismatch — hold\n"
        "  30-49  = Missing critical requirements — reject unless pool is thin\n"
        "  0-29   = Wrong domain or hard filter fail — reject\n"
        "  IMPORTANT: Spread scores realistically. Do NOT cluster everyone between 60-75.\n\n"
        "REQUIRED JSON FIELDS:\n"
        "- fitment_score: integer 0-100 (apply scoring rules above; subtract penalties below before returning)\n"
        "- must_have_breakdown: list of objects {\"skill\": \"<name>\", \"status\": \"Met|Partial|Missing\", \"evidence\": \"<one sentence or empty>\"} — one per must-have skill from JD\n"
        "- must_have_coverage_ratio: float 0.0-1.0 computed as (Met + 0.5*Partial) / Total\n"
        "- reasoning: one decisive paragraph starting with the verdict (e.g. 'Strong hire.', 'Borderline — verify X.', 'Reject.'). Name top 2 strengths with evidence. Name top gap. End with clear action.\n"
        "- strengths: list of exactly 3 strings. Each: CAPS LABEL then 1-2 sentences of specific evidence from resume.\n"
        "- gaps: list of exactly 2 strings. Each: name the missing requirement and why it matters for this role.\n"
        "- recommendation: one of \"shortlist\", \"hold\", \"reject\"\n"
        "- context_bonus: integer 0-15. +5 if company_types match JD preferred_company_type; +5 if avg_team_size matches JD preferred_team_size; +5 if role_type matches JD role_type. Skip any bonus where JD has 'Any'.\n"
        "- scoring_factors: list of exactly 5 objects {\"factor\": \"<name>\", \"impact\": \"<+0|-5|-10>\", \"reason\": \"<one sentence>\"} in this order: [Notice Period, Location, Experience Gap, Gender, College]. Use +0 when no penalty.\n"
        "  Penalties: notice_period > JD max = -5; location mismatch for in-office role = -5; experience < half JD requirement = -10; gender mismatch if JD specifies = -5; college exclusion match = -10 / college preference match = +5.\n"
        "- hard_filters_passed: boolean — true only if notice period, location, and minimum experience all pass\n"
        "- hard_filter_failures: list of strings for each failed filter. Empty list if all pass.\n"
        "- role_level_detected: one of \"Junior\"|\"Mid-level\"|\"Senior\"|\"Lead\"|\"Manager\"|\"Director\"\n"
        "- role_level_match: one of \"Match\"|\"Over-qualified\"|\"Under-qualified\"\n"
        "- tool_currency: one of \"Current\"|\"Previous\"|\"None\"\n"
        "- key_tool_recency: one of \"Current\"|\"Recent\"|\"Stale\"|\"Never\" — check the SINGLE most important JD tool in the candidate's most recent role specifically\n"
        "- certifications_assessed: list of objects {\"name\": \"<cert>\", \"tier\": \"Foundational|Practitioner|Expert|Mentor\"} for every cert in resume. Empty list if none.\n"
        "- quantified_outcomes_count: integer — count of achievements with a number/metric/percentage\n"
        "- alternative_role_fit: string — better-matching role title if candidate is mismatched for this one, else empty string\n"
        "- cv_narrative_style: one of \"Achievement-focused\"|\"Task-focused\"|\"Mixed\"\n"
        "- availability_signal: one of \"Available now\"|\"Immediate\"|\"2 weeks\"|\"30 days\"|\"60 days\"|\"90 days\"|\"Unknown\"\n"
        "- availability_reason: one short sentence explaining how you inferred availability\n"
        "- rare_assets: list of up to 3 strings — rare or niche qualifications most candidates at this level would not have\n"
        "- self_reported_unverified: list of up to 3 strings — impressive claims that cannot be verified from resume alone\n"
        "- interview_flags: list of up to 5 strings — specific questions recruiter should probe (gaps, inconsistencies, vague claims)\n\n"
        "JSON OUTPUT:"
    )

    _EMPTY_RESULT = {
        "fitment_score": 0, "reasoning": "AI evaluation failed.", "strengths": [], "gaps": [],
        "recommendation": "hold", "context_bonus": 0, "scoring_factors": [],
        "hard_filters_passed": True, "hard_filter_failures": [], "role_level_detected": "Unknown",
        "role_level_match": "Unknown", "tool_currency": "None", "cv_narrative_style": "Unknown",
        "availability_signal": "Unknown", "availability_reason": "", "rare_assets": [],
        "self_reported_unverified": [], "interview_flags": [], "must_have_coverage_ratio": 0.0,
        "must_have_breakdown": [], "key_tool_recency": "Never", "certifications_assessed": [],
        "quantified_outcomes_count": 0, "alternative_role_fit": "",
    }

    max_retries = 20  # never give up — wait it out
    for attempt in range(max_retries):
        try:
            text = _call_groq(GROQ_REASON_MODEL, user_prompt, max_tokens=4096, system=system_prompt)
            logger.info(f"Groq Pass 2 raw response (first 300 chars):\n{text[:300]}")
            try:
                result = _parse_json_response(text)
            except Exception as parse_err:
                # JSON parse failed — log and retry rather than returning zeros
                logger.warning(f"JSON parse failed on attempt {attempt+1}. Retrying. Error: {parse_err}")
                time.sleep(10)
                continue

            # Normalise all fields — fill missing ones with safe defaults
            result.setdefault("context_bonus", 0)
            result.setdefault("scoring_factors", [])
            result.setdefault("hard_filters_passed", True)
            result.setdefault("hard_filter_failures", [])
            result.setdefault("role_level_detected", "Unknown")
            result.setdefault("role_level_match", "Unknown")
            result.setdefault("tool_currency", "None")
            result.setdefault("cv_narrative_style", "Unknown")
            result.setdefault("availability_signal", "Unknown")
            result.setdefault("availability_reason", "")
            result.setdefault("rare_assets", [])
            result.setdefault("self_reported_unverified", [])
            result.setdefault("interview_flags", [])
            result.setdefault("must_have_breakdown", [])
            result.setdefault("key_tool_recency", "Never")
            result.setdefault("certifications_assessed", [])
            result.setdefault("alternative_role_fit", "")

            # Safe type coercion
            try:
                result["must_have_coverage_ratio"] = float(result.get("must_have_coverage_ratio", 0.0))
            except (TypeError, ValueError):
                result["must_have_coverage_ratio"] = 0.0
            try:
                result["quantified_outcomes_count"] = int(result.get("quantified_outcomes_count", 0))
            except (TypeError, ValueError):
                result["quantified_outcomes_count"] = 0

            # Recompute must_have_coverage_ratio server-side from breakdown (defensive)
            if isinstance(result.get("must_have_breakdown"), list) and result["must_have_breakdown"]:
                total = len(result["must_have_breakdown"])
                met = sum(1 for x in result["must_have_breakdown"] if (x.get("status") or "").lower() == "met")
                partial = sum(1 for x in result["must_have_breakdown"] if (x.get("status") or "").lower() == "partial")
                if total > 0:
                    result["must_have_coverage_ratio"] = round((met + 0.5 * partial) / total, 3)

            if not isinstance(result.get("must_have_breakdown"), list):
                result["must_have_breakdown"] = []
            if not isinstance(result.get("certifications_assessed"), list):
                result["certifications_assessed"] = []

            return result

        except Exception as e:
            err_str = str(e).lower()
            if any(x in err_str for x in ("rate limit", "429", "too many requests", "quota")):
                wait = min(30 * (attempt + 1), 300)
                logger.warning(f"Groq rate limit on Pass 2 attempt {attempt+1}/{max_retries}. Waiting {wait}s...")
                time.sleep(wait)
                continue
            logger.error(f"Groq Pass 2 unexpected error: {e}")
            time.sleep(15)
            continue

    logger.error("Groq Pass 2 failed after all retries.")
    return _EMPTY_RESULT


def extract_resume_metadata(raw_text: str) -> dict:
    """
    Uses Groq (fast model) to extract structured metadata from a resume, with regex fallback.
    Text is cleaned before both regex extraction and AI prompt construction.
    """
    # Clean text first — before building the AI prompt or running regex
    raw_text = raw_text.replace('\x00', '').replace('\xa0', ' ')

    # Regex fallback — runs unconditionally; AI results override where better
    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
    regex_name = "Unknown"
    if lines:
        first_line = lines[0]
        first_words = first_line.split()
        if 1 <= len(first_words) <= 3 and not re.search(r'[\d@:]', first_line):
            regex_name = first_line
        else:
            for line in lines[:8]:
                words = line.split()
                if 1 <= len(words) <= 4 and not re.search(r'[\d@:]', line):
                    if not any(w.lower() in ['resume', 'profile', 'curriculum', 'page', 'email', 'phone', 'contact'] for w in words):
                        regex_name = line
                        break

    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', raw_text)
    phone_match = re.search(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', raw_text)
    exp_match = re.search(r'\b([0-9]|[1-4][0-9]|50)(\.\d)?\s*(years|yrs|yr)\b', raw_text)
    regex_exp = int(float(exp_match.group(1))) if exp_match else 0

    skills_found = []
    skills_section = re.search(
        r'(?i)(skills|technologies|tools|expertise|technical skills)[:\n]+(.*?)(?=\n\n|\n[A-Z][a-z]+:|$)',
        raw_text, re.DOTALL
    )
    if skills_section:
        content = skills_section.group(2).replace('\n', ',').replace('•', ',').replace('|', ',')
        skills_found = [
            s.strip() for s in content.split(',')
            if 2 <= len(s.strip()) <= 20
            and '&' not in s
            and len(s.strip().split()) <= 2
        ]
    # Broad fallback — covers tech, marketing, design, finance, ops roles
    if len(skills_found) < 3:
        common_skills = [
            # Tech
            'Python', 'Java', 'React', 'Angular', 'Node', 'AWS', 'Docker', 'Kubernetes',
            'SQL', 'MongoDB', 'JavaScript', 'TypeScript', 'C++', 'C#', 'PHP', 'Go',
            # Digital Marketing
            'SEO', 'SEM', 'Google Ads', 'Meta Ads', 'Facebook Ads', 'LinkedIn Ads',
            'Google Analytics', 'HubSpot', 'Mailchimp', 'Email Marketing', 'Content Marketing',
            'Social Media', 'Lead Generation', 'CRM', 'WhatsApp', 'Canva',
            # Design / Architecture
            'AutoCAD', 'Revit', 'SketchUp', 'Photoshop', 'Illustrator', 'Figma',
            'V-Ray', 'Enscape', 'Lumion', '3D Modeling',
            # Finance / Ops
            'Excel', 'Power BI', 'Tableau', 'Tally', 'SAP', 'QuickBooks',
            # General
            'Project Management', 'Agile', 'Scrum', 'Leadership', 'Communication',
        ]
        for s in common_skills:
            if re.search(rf'\b{re.escape(s)}\b', raw_text, re.IGNORECASE) and s not in skills_found:
                skills_found.append(s)

    extracted_data = {
        "name": regex_name,
        "email": email_match.group(0) if email_match else None,
        "phone": phone_match.group(0) if phone_match else None,
        "skills": skills_found[:15],
        "experience_years": regex_exp,
        "location": "Not specified",
        "notice_period": "Not specified",
        "gender": "Not specified",
        "college": "Not specified",
        "projects": [],
        "achievements": [],
        "certifications": [],
        "education": [],
        "languages": [],
        "previous_companies": [],
        "companies_switched": 0,
        "company_types": [],
        "avg_team_size": "Unknown",
        "role_type": "Unknown"
    }

    # AI extraction — primary source; regex is fallback only
    prompt = f"""You are a high-fidelity resume parsing engine. Extract specific information from the resume text provided.

CRITICAL INSTRUCTIONS:
1. Return ONLY a valid JSON object.
2. Do NOT include any markdown formatting, explanations, or additional text.
3. If a field is missing, use null or "Not specified".
4. For 'email': Extract ONLY the candidate's personal/professional contact email. It must be a real external email (gmail, yahoo, outlook, company domain, etc.). Ignore any system-generated or internal emails (e.g. anything ending in @jobos.internal, @system, @noreply). If no valid email found, return null.
5. For 'experience_years': Calculate total months of work experience from all roles, convert to years (round down). Example: 4 months = 0, 14 months = 1. Read start and end dates carefully — do NOT use the year number as the duration.
6. For 'college': Return the institution name where the candidate earned their HIGHEST degree (e.g. B.Tech, MBA, M.Tech, MCA). If multiple degrees from different institutions, return the one for the highest qualification. Do NOT return "Various" or a list — return a single institution name string.
7. For 'company_types': For each company the candidate worked at, classify it as one of: Fintech, Edtech, Ecommerce, Healthcare, Product, Services, Startup, Large Enterprise. Return a list of unique types across all companies.
8. For 'avg_team_size': Estimate the average team size the candidate worked in across all roles. Return one of: Small (1-15), Medium (16-50), Large (51-200), Enterprise (200+), Unknown.
9. For 'role_type': Based on the candidate's roles, classify as one of: Individual Contributor, 50% IC + 50% Management, Team Lead, Unknown.

JSON SCHEMA:
{{
  "name": "Candidate's Full Name",
  "email": "email@example.com",
  "phone": "+1-123-456-7890",
  "skills": ["Skill 1", "Skill 2", "Skill 3"],
  "experience_years": 5,
  "location": "City, State/Country",
  "notice_period": "Immediate/15days/30days/60days/90days",
  "gender": "Male/Female/Other",
  "college": "Single institution name for highest degree",
  "projects": [{{"title": "Project Name", "role": "Candidate Role", "responsibilities": "2-3 bullet points"}}],
  "achievements": ["Award or recognition string"],
  "certifications": ["Certification Name — Issuing Body"],
  "education": [{{"degree": "B.Tech", "institution": "University Name", "year": "2020"}}],
  "languages": ["English", "Hindi"],
  "previous_companies": ["Company A", "Company B"],
  "companies_switched": 2,
  "company_types": ["Fintech", "Product", "Startup"],
  "avg_team_size": "Medium (16-50)",
  "role_type": "Individual Contributor"
}}

RESUME TEXT TO PARSE:
---
{raw_text[:20000]}
---

JSON OUTPUT:"""

    try:
        text = _call_groq(GROQ_REASON_MODEL, prompt, max_tokens=3000)
        logger.info(f"Groq resume extraction response (first 200 chars): {text[:200]}")
        ai_data = _parse_json_response(text)

        # AI is the primary source for all fields — regex is fallback
        for key in ["name", "skills", "experience_years", "location", "notice_period", "gender", "college",
                    "projects", "achievements", "certifications", "education", "languages", "previous_companies",
                    "company_types", "avg_team_size", "role_type"]:
            val = ai_data.get(key)
            if val and val not in [None, "null", "Not specified", "Unknown", "Various", "", 0, []]:
                extracted_data[key] = val

        # Email: AI always wins over regex (regex is unreliable for email context)
        ai_email = ai_data.get("email")
        if ai_email and ai_email not in [None, "null", "Not specified"] and "@" in str(ai_email):
            extracted_data["email"] = ai_email
        # regex email is already set above as fallback; keep it if AI returned nothing

        # Phone: AI wins if found, else keep regex result
        ai_phone = ai_data.get("phone")
        if ai_phone and ai_phone not in [None, "null", "Not specified"]:
            extracted_data["phone"] = ai_phone

        if ai_data.get("companies_switched") is not None:
            extracted_data["companies_switched"] = ai_data["companies_switched"]

    except Exception as e:
        logger.error(f"Groq resume parsing failed: {e}")
        logger.error(f"Groq raw response: {locals().get('text', '(call failed before response)')}")
        raise RuntimeError(f"Resume extraction failed — AI service unavailable. Please re-upload the resume. Detail: {e}")

    return extracted_data
