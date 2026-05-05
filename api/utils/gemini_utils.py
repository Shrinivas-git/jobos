import os
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
import re
import json
import logging
import time
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

# Initialize Groq client
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if GROQ_API_KEY:
    ai_client = Groq(api_key=GROQ_API_KEY)
else:
    logger.warning("GROQ_API_KEY not found in environment variables.")
    ai_client = None

FAST_MODEL = "llama-3.1-8b-instant"
REASON_MODEL = "llama-3.3-70b-versatile"


def _call_groq(model: str, prompt: str, max_tokens: int = 2048) -> str:
    if not ai_client:
        raise RuntimeError("Groq client not initialized — GROQ_API_KEY missing.")
    response = ai_client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


def _parse_json_response(text: str) -> dict:
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise


def extract_jd_data(raw_text: str) -> dict:
    """Uses Groq (fast model) to extract structured fields from raw JD text."""
    prompt = f"""You are a high-precision recruitment AI. Extract structured data from the following raw Job Description (JD) text.
Return ONLY a valid JSON object. Do not include markdown formatting or explanations.

Fields to extract:
- title: Job Title
- level: Seniority level (e.g. Junior, Senior, Lead, Manager)
- responsibilities: Core responsibilities of the role
- kpis: Key Performance Indicators if mentioned, else "Not specified"
- skills: List of specific technical and soft skills
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
        return _parse_json_response(text)
    except Exception as e:
        logger.error(f"Error extracting JD data with Groq: {e}")
        return {
            "title": "Extraction Failed",
            "level": "Unknown",
            "responsibilities": raw_text[:500],
            "kpis": "Not specified",
            "skills": [],
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


def evaluate_candidate_fitment(jd_structured_data: dict, resume_text: str) -> dict:
    """
    Pass 2: Uses Groq (reason model) to perform deep reasoning on a candidate's fitment for a JD.
    Includes contextual bonus scoring based on company type, team size, and role type alignment.
    """
    if not ai_client:
        raise RuntimeError("Groq client not initialized — GROQ_API_KEY missing.")

    jd_text = json.dumps(jd_structured_data, indent=2)

    try:
        response = ai_client.chat.completions.create(
            model=REASON_MODEL,
            max_tokens=1536,
            messages=[
                {
                    "role": "system",
                    "content": f"You are an expert senior technical recruiter.\n\nJOB DESCRIPTION FOR THIS EVALUATION:\n{jd_text}"
                },
                {
                    "role": "user",
                    "content": (
                        f"Evaluate the following candidate resume against the job description above.\n\n"
                        f"CANDIDATE RESUME:\n---\n{resume_text[:12000]}\n---\n\n"
                        "Return ONLY a valid JSON object. No markdown. Be objective and critical.\n"
                        "- fitment_score: integer 0-100. Apply the additional scoring factors below before returning this value.\n"
                        "- reasoning: one concise paragraph\n"
                        "- strengths: list of exactly 5 strings, each 1-2 sentences with specific evidence from the resume explaining why it is a strength\n"
                        "- gaps: list of exactly 5 strings, each 1-2 sentences explaining what is missing and why it matters for this role\n"
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
                        "  Use \"+0\" when no penalty applies. Always include all 5 regardless of impact.\n\n"
                        "JSON OUTPUT:"
                    )
                }
            ]
        )
        text = response.choices[0].message.content.strip()
        time.sleep(2)
        logger.info(f"Groq Pass 2 response (first 200 chars): {text[:200]}")
        result = _parse_json_response(text)
        if "context_bonus" not in result:
            result["context_bonus"] = 0
        if "scoring_factors" not in result:
            result["scoring_factors"] = []
        return result
    except Exception as e:
        logger.error(f"Groq Pass 2 reasoning failed: {e}")
        return {
            "fitment_score": 0,
            "reasoning": "AI evaluation failed.",
            "strengths": [],
            "gaps": [],
            "recommendation": "hold",
            "context_bonus": 0,
            "scoring_factors": []
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

    # AI extraction — overrides regex results where the AI gives a better answer
    prompt = f"""You are a high-fidelity resume parsing engine. Extract specific information from the resume text provided.

CRITICAL INSTRUCTIONS:
1. Return ONLY a valid JSON object.
2. Do NOT include any markdown formatting, explanations, or additional text.
3. If a field is missing, use null or "Not specified".
4. For 'experience_years': Calculate total months of work experience from all roles, convert to years (round down). Example: 4 months = 0, 14 months = 1. Read start and end dates carefully — do NOT use the year number as the duration.
5. For 'company_types': For each company the candidate worked at, classify it as one of: Fintech, Edtech, Ecommerce, Healthcare, Product, Services, Startup, Large Enterprise. Return a list of unique types across all companies.
6. For 'avg_team_size': Estimate the average team size the candidate worked in across all roles. Return one of: Small (1-15), Medium (16-50), Large (51-200), Enterprise (200+), Unknown.
7. For 'role_type': Based on the candidate's roles, classify as one of: Individual Contributor, 50% IC + 50% Management, Team Lead, Unknown.

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
  "college": "University Name",
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
        text = _call_groq(FAST_MODEL, prompt)
        logger.info(f"Groq resume extraction response (first 200 chars): {text[:200]}")
        ai_data = _parse_json_response(text)

        for key in ["name", "skills", "experience_years", "location", "notice_period", "gender", "college",
                    "projects", "achievements", "certifications", "education", "languages", "previous_companies",
                    "company_types", "avg_team_size", "role_type"]:
            val = ai_data.get(key)
            if val and val not in [None, "null", "Not specified", "Unknown", "", 0, []]:
                extracted_data[key] = val
        if ai_data.get("email") and not extracted_data["email"]:
            extracted_data["email"] = ai_data["email"]
        if ai_data.get("phone") and not extracted_data["phone"]:
            extracted_data["phone"] = ai_data["phone"]
        if ai_data.get("companies_switched") is not None:
            extracted_data["companies_switched"] = ai_data["companies_switched"]

    except Exception as e:
        logger.error(f"Groq resume parsing failed, using regex fallback: {e}")
        logger.error(f"Groq raw response: {locals().get('text', '(call failed before response)')}")

    return extracted_data
