import os
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
import re
import json
import logging
import time
import anthropic
from groq import Groq
from typing import List
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Initialize local embedding model
try:
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    logger.info("Local embedding model (all-MiniLM-L6-v2) loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load local embedding model: {e}")
    embedding_model = None

# Anthropic — used ONLY for Pass 2 matching (REASON_MODEL)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if ANTHROPIC_API_KEY:
    ai_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
else:
    logger.warning("ANTHROPIC_API_KEY not found — Pass 2 matching will fail.")
    ai_client = None

# Groq — used for all other AI calls (JD extraction, resume extraction, assessments, CRM, feedback)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)
else:
    logger.warning("GROQ_API_KEY not found — non-matching AI calls will fail.")
    groq_client = None

FAST_MODEL = "llama-3.1-8b-instant"       # Groq — JD extraction, resume extraction, embeddings
REASON_MODEL = "claude-sonnet-4-6"         # Anthropic — Pass 2 matching only
GROQ_REASON_MODEL = "llama-3.3-70b-versatile"  # Groq — assessments scoring, CRM, feedback


def _call_groq(model: str, prompt: str, max_tokens: int = 2048) -> str:
    """Groq call — used for all non-matching AI tasks."""
    if not groq_client:
        raise RuntimeError("Groq client not initialized — GROQ_API_KEY missing.")
    response = groq_client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


def _call_claude(model: str, prompt: str, max_tokens: int = 2048) -> str:
    """Anthropic call — used ONLY for Pass 2 matching (REASON_MODEL)."""
    if not ai_client:
        raise RuntimeError("Anthropic client not initialized — ANTHROPIC_API_KEY missing.")
    response = ai_client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


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
        text = _call_groq(FAST_MODEL, prompt)
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
        text = _call_groq(FAST_MODEL, prompt)
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
    Pass 2: Uses Claude (reason model) to perform deep reasoning on a candidate's fitment for a JD.
    Includes contextual bonus scoring based on company type, team size, and role type alignment.
    """
    if not ai_client:
        raise RuntimeError("Anthropic client not initialized — ANTHROPIC_API_KEY missing.")

    jd_text = json.dumps(jd_structured_data, indent=2)

    try:
        response = ai_client.messages.create(
            model=REASON_MODEL,
            max_tokens=2048,
            system=f"You are an expert senior technical recruiter.\n\nJOB DESCRIPTION FOR THIS EVALUATION:\n{jd_text}",
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Evaluate the following candidate resume against the job description above.\n\n"
                        f"CANDIDATE RESUME:\n---\n{resume_text[:12000]}\n---\n\n"
                        "Return ONLY a valid JSON object. No markdown.\n"
                        "TONE: Write like a senior recruiter making a hiring call — decisive, specific, action-oriented. "
                        "Lead with what matters most. Use phrases like 'interview immediately', 'strong hire', 'borderline — verify X before proceeding', 'reject — wrong level'. "
                        "Do NOT write like a technical analyst listing observations. Every sentence must drive a hiring decision.\n"
                        "CRITICAL JSON RULES: Inside any string value, do NOT use unescaped double quotes. "
                        "If you need to quote something, use single quotes ('like this') or escape with backslash. "
                        "Example: write \"managing 'Business Critical' production environments\" — NOT \"managing \"Business Critical\" production environments\".\n"
                        "- fitment_score: integer 0-100. Apply the additional scoring factors below before returning this value.\n"
                        "SCORING CALIBRATION:\n"
                        "  90-100 = Strong hire, meets all must-haves with verified evidence — interview immediately\n"
                        "  70-89  = Good candidate, meets most must-haves, 1-2 gaps — shortlist and verify gaps\n"
                        "  50-69  = Borderline, role level mismatch or key tool gap — hold pending clarification\n"
                        "  30-49  = Wrong role level or missing critical experience — reject unless pool is thin\n"
                        "  0-29   = Wrong domain or fails hard filters — reject\n"
                        "  Do NOT cluster scores around 62-72. Spread scores based on actual evidence.\n"
                        "SIGNAL PRIORITISATION: When writing strengths, always surface the highest-signal differentiators first — "
                        "e.g. Salesforce Premier Support escalation experience, CoE establishment, multi-tenant architecture depth, "
                        "quantified production outcomes (zero outages, deployment count). These outweigh generic skill mentions.\n"
                        "MUST-HAVE COVERAGE:\n"
                        "  Use the JD's must_have_skills list (fall back to skills list if must_have_skills is empty).\n"
                        "  For each must-have, classify as Met / Partial / Missing with one short evidence sentence quoting the resume.\n"
                        "- must_have_breakdown: list of objects, one per must-have. Each object: {\"skill\": \"<must-have>\", \"status\": \"Met|Partial|Missing\", \"evidence\": \"<one short sentence; empty string if Missing>\"}.\n"
                        "- must_have_coverage_ratio: float 0-1. Compute as (Met_count + 0.5 × Partial_count) / Total_must_haves. Return 0.0 if no must-haves.\n"
                        "- reasoning: one decisive paragraph written like a senior recruiter's verbal summary to a hiring manager. "
                        "Start with the hiring verdict (e.g. 'Strong hire — interview immediately.' or 'Borderline — hold until X is verified.'). "
                        "Name the 2-3 highest-signal strengths with specific evidence. Name the 1-2 most disqualifying gaps. End with a clear action.\n"
                        "- strengths: list of exactly 3 strings. Each string: start with a bold label in CAPS (e.g. 'COPADO MASTERY:'), then 1-2 sentences of specific evidence from the resume with metrics or named outcomes where possible. Prioritise differentiating signals over generic skills.\n"
                        "- gaps: list of exactly 2 strings. Each string: name the missing requirement clearly and explain why it is disqualifying or risky for THIS specific role.\n"
                        "- recommendation: one of \"shortlist\", \"hold\", \"reject\"\n"
                        "- context_bonus: integer 0-15 calculated as follows:\n"
                        "  +5 if candidate's company_types includes any type from JD preferred_company_type\n"
                        "  +5 if candidate's avg_team_size matches JD preferred_team_size\n"
                        "  +5 if candidate's role_type matches JD role_type\n"
                        "  (If JD has 'Any' or no preference for a field, do not apply that bonus)\n"
                        "- Additional scoring factors (subtract from fitment_score before returning it):\n"
                        "  - Notice period: if candidate notice_period exceeds JD max_notice_period, subtract 5 points\n"
                        "  - Location: if JD work_structure is In-office and candidate location does not match JD location, subtract 5 points\n"
                        "  - Experience gap: if candidate experience_years is less than half of JD relevant_experience, subtract 10 points\n"
                        "  - Gender: if JD gender_preference is not Any and does not match candidate gender, subtract 5 points\n"
                        "  - College: if JD college_exclusion contains candidate college, subtract 10 points; else if JD college_preference is set and candidate college matches any preferred college, add 5 points\n"
                        "- scoring_factors: list of exactly 5 objects, one per factor above, in this order: Notice Period, Location, Experience Gap, Gender, College.\n"
                        "  Each object: {\"factor\": \"<name>\", \"impact\": \"<+0 or -5 or -10>\", \"reason\": \"<one sentence>\"}\n"
                        "  Use \"+0\" when no penalty applies. Always include all 5 regardless of impact.\n"
                        "- hard_filters_passed: boolean. True only if candidate passes ALL three hard filters: (1) notice_period within JD limit if specified, (2) location matches JD if work_structure is In-office, (3) experience_years >= half of JD relevant_experience.\n"
                        "- hard_filter_failures: list of strings naming each hard filter that failed (e.g. \"Notice period too long\", \"Location mismatch\", \"Experience below minimum\"). Empty list if all pass.\n"
                        "- role_level_detected: string. The actual operating level of the candidate based on their responsibilities and seniority. One of: \"Junior\", \"Mid-level\", \"Senior\", \"Lead\", \"Manager\", \"Director\".\n"
                        "- role_level_match: string. Compare role_level_detected against the JD level field. One of: \"Match\", \"Over-qualified\", \"Under-qualified\".\n"
                        "- tool_currency: string. Are the candidate's primary tools and frameworks still actively used in the industry today? One of: \"Current\" (tools are modern and in active use), \"Previous\" (tools are older or being phased out in the industry), \"None\" (cannot assess from resume).\n"
                        "- key_tool_recency: string. Identify the SINGLE most important tool/framework from the JD (e.g. Copado for a Salesforce DevOps JD). Check if it appears in the candidate's MOST RECENT role specifically (not just somewhere in their history). One of: \"Current\" (used in current/most-recent role), \"Recent\" (used in role within the last 2 years but not the most recent), \"Stale\" (only used >2 years ago or in earlier roles), \"Never\" (no evidence of using it).\n"
                        "- certifications_assessed: list of objects, one per certification found in the resume. Each object: {\"name\": \"<cert name>\", \"tier\": \"Foundational|Practitioner|Expert|Mentor\"}. Foundational = entry-level/associate/fundamentals; Practitioner = mid-level/professional/admin; Expert = senior/architect/consultant/specialist with proven depth; Mentor = peer-recognised programs (e.g. Copado Mentor, Salesforce MVP). Empty list if none.\n"
                        "- quantified_outcomes_count: integer. Count of distinct achievements in the resume that include a metric (percentage, dollar amount, count, time saved, scale figure). Example: \"reduced deployment time by 35%\" counts as 1.\n"
                        "- alternative_role_fit: string. If the candidate is strong but mismatched for THIS role's level/scope, suggest the role they would actually fit (e.g. \"Senior Salesforce Developer\", \"Salesforce Architect\", \"Junior Release Engineer\"). Empty string if they are a fit for this role or not strong enough for any alternative.\n"
                        "- cv_narrative_style: string. How is the CV written? One of: \"Achievement-focused\" (uses metrics, outcomes, quantified impact), \"Task-focused\" (describes duties and responsibilities without outcomes), \"Mixed\".\n"
                        "- availability_signal: string. When can the candidate realistically start? Derive from latest role end-date FIRST (if end-date is in the past, mark \"Available now\"), else from stated notice period. Examples: \"Available now\", \"Immediate\", \"2 weeks\", \"30 days\", \"60 days\", \"90 days\", \"Unknown\".\n"
                        "- availability_reason: string. One short sentence explaining how you inferred availability (e.g. \"Latest role ended March 2026 — currently between roles\", \"Resume states 30-day notice period\").\n"
                        "- rare_assets: list of up to 3 strings. Unique or rare qualifications that most candidates at this level would not have — niche certifications, rare domain expertise, unusual or highly specialised tech stacks, or high-signal industry achievements. Empty list if none found.\n"
                        "- self_reported_unverified: list of up to 3 strings. Claims in the resume that appear impressive but cannot be independently verified from the document content alone — e.g. large revenue impact claims without metrics, leadership claims without team size evidence, unverified awards. Empty list if none identified.\n"
                        "- interview_flags: list of up to 5 strings. Specific questions or topics a recruiter should probe during the interview based on observed inconsistencies, unexplained gaps, or vague claims. Each string is a short actionable probe (e.g. \"Ask about the 2-year gap between Company A and B\", \"Probe actual hands-on depth with Kubernetes\").\n\n"
                        + (
                            f"RECRUITER'S ADDITIONAL NOTES ABOUT THE IDEAL CANDIDATE:\n{recruiter_notes}\n"
                            "Consider this while evaluating fitment. If the candidate clearly contradicts these notes, penalize fitment. "
                            "If they strongly match, reward fitment.\n\n"
                            if recruiter_notes and recruiter_notes.strip() else ""
                        )
                        + "JSON OUTPUT:"
                    )
                }
            ]
        )
        text = response.content[0].text.strip()
        time.sleep(2)
        logger.info(f"Claude Pass 2 raw response:\n{text}")
        try:
            result = _parse_json_response(text)
        except Exception as parse_err:
            logger.error(f"JSON parse failed for Pass 2 response. Error: {parse_err}\nRaw text was:\n{text}")
            raise
        if "context_bonus" not in result:
            result["context_bonus"] = 0
        if "scoring_factors" not in result:
            result["scoring_factors"] = []
        if "hard_filters_passed" not in result:
            result["hard_filters_passed"] = True
        if "hard_filter_failures" not in result:
            result["hard_filter_failures"] = []
        if "role_level_detected" not in result:
            result["role_level_detected"] = "Unknown"
        if "role_level_match" not in result:
            result["role_level_match"] = "Unknown"
        if "tool_currency" not in result:
            result["tool_currency"] = "None"
        if "cv_narrative_style" not in result:
            result["cv_narrative_style"] = "Unknown"
        if "availability_signal" not in result:
            result["availability_signal"] = "Unknown"
        if "rare_assets" not in result:
            result["rare_assets"] = []
        if "self_reported_unverified" not in result:
            result["self_reported_unverified"] = []
        if "interview_flags" not in result:
            result["interview_flags"] = []
        if "must_have_coverage_ratio" not in result:
            result["must_have_coverage_ratio"] = 0.0
        try:
            result["must_have_coverage_ratio"] = float(result["must_have_coverage_ratio"])
        except (TypeError, ValueError):
            result["must_have_coverage_ratio"] = 0.0
        if "must_have_breakdown" not in result or not isinstance(result["must_have_breakdown"], list):
            result["must_have_breakdown"] = []
        # Server-side recompute of must_have_coverage_ratio from breakdown when available (defensive)
        if result["must_have_breakdown"]:
            total = len(result["must_have_breakdown"])
            met = sum(1 for x in result["must_have_breakdown"] if (x.get("status") or "").lower() == "met")
            partial = sum(1 for x in result["must_have_breakdown"] if (x.get("status") or "").lower() == "partial")
            if total > 0:
                result["must_have_coverage_ratio"] = (met + 0.5 * partial) / total
        if "key_tool_recency" not in result:
            result["key_tool_recency"] = "Never"
        if "certifications_assessed" not in result or not isinstance(result["certifications_assessed"], list):
            result["certifications_assessed"] = []
        if "quantified_outcomes_count" not in result:
            result["quantified_outcomes_count"] = 0
        try:
            result["quantified_outcomes_count"] = int(result["quantified_outcomes_count"])
        except (TypeError, ValueError):
            result["quantified_outcomes_count"] = 0
        if "alternative_role_fit" not in result:
            result["alternative_role_fit"] = ""
        if "availability_reason" not in result:
            result["availability_reason"] = ""
        return result
    except Exception as e:
        logger.error(f"Claude Pass 2 reasoning failed: {e}")
        return {
            "fitment_score": 0,
            "reasoning": "AI evaluation failed.",
            "strengths": [],
            "gaps": [],
            "recommendation": "hold",
            "context_bonus": 0,
            "scoring_factors": [],
            "hard_filters_passed": True,
            "hard_filter_failures": [],
            "role_level_detected": "Unknown",
            "role_level_match": "Unknown",
            "tool_currency": "None",
            "cv_narrative_style": "Unknown",
            "availability_signal": "Unknown",
            "rare_assets": [],
            "self_reported_unverified": [],
            "interview_flags": [],
            "must_have_coverage_ratio": 0.0,
            "must_have_breakdown": [],
            "key_tool_recency": "Never",
            "certifications_assessed": [],
            "quantified_outcomes_count": 0,
            "alternative_role_fit": "",
            "availability_reason": ""
        }


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
    if len(skills_found) < 3:
        common_skills = [
            'Python', 'Java', 'React', 'Angular', 'Node', 'AWS', 'Docker', 'Kubernetes',
            'SQL', 'NoSQL', 'MongoDB', 'JavaScript', 'TypeScript', 'C++', 'C#', 'PHP', 'Go', 'Rust'
        ]
        for s in common_skills:
            if re.search(rf'\b{s}\b', raw_text, re.IGNORECASE) and s not in skills_found:
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
{raw_text[:10000]}
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
