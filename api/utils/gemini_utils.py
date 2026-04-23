import os
import json
import logging
import google.generativeai as genai
from typing import List, Optional
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Initialize local embedding model
try:
    # This will download the model on first run/build
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    logger.info("Local embedding model (all-MiniLM-L6-v2) loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load local embedding model: {e}")
    embedding_model = None

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY not found in environment variables.")

def extract_jd_data(raw_text: str) -> dict:
    """
    Uses Gemini 2.5 Pro to extract structured fields from raw JD text.
    """
    model = genai.GenerativeModel('gemini-2.5-pro')
    
    prompt = f"""
    You are a high-precision recruitment AI. Extract structured data from the following raw Job Description (JD) text.
    Return ONLY a valid JSON object. Do not include markdown formatting or explanations.
    
    Fields to extract:
    - title: Job Title
    - level: Seniority level (e.g. Junior, Senior, Lead, Manager)
    - responsibilities: Core responsibilities of the role
    - kpis: Key Performance Indicators if mentioned, else "Not specified"
    - skills: List of specific technical and soft skills
    - experience_range: Required years of experience (e.g. "3-5 years")
    - compensation_range: Salary range if mentioned, else "Not specified"
    - work_structure: In-office, Hybrid, or Remote
    - location: Specific city/region
    - hiring_timeline: e.g. "Immediate", "2 weeks", "Not specified"
    - urgency: Low, Medium, High, or Critical
    - num_positions: Number of open positions (integer), default to 1 if not mentioned
    
    Raw JD Text:
    ---
    {raw_text}
    ---
    
    JSON Output:
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:-3].strip()
        elif text.startswith("```"):
            text = text[3:-3].strip()
            
        return json.loads(text)
    except Exception as e:
        logger.error(f"Error extracting JD data with Gemini: {e}")
        return {
            "title": "Extraction Failed",
            "level": "Unknown",
            "responsibilities": raw_text[:500],
            "kpis": "Not specified",
            "skills": [],
            "experience_range": "Not specified",
            "compensation_range": "Not specified",
            "work_structure": "Not specified",
            "location": "Not specified",
            "hiring_timeline": "Not specified",
            "urgency": "Medium",
            "num_positions": 1
        }

def generate_jd_formats(structured_data: dict) -> dict:
    """
    Uses Gemini to generate Internal, Short, and Candidate Markdown formats.
    """
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    Based on the following structured Job Description data, generate three distinct Markdown formats.
    Return ONLY a valid JSON object with keys: "internal", "short", "candidate".
    
    1. "internal": Full detail including salary, hiring timeline, and internal notes.
    2. "short": Recruiter-facing summary (title, key skills, level, location).
    3. "candidate": Candidate-facing description. IMPORTANT: Exclude specific salary figures (use "Competitive") and remove sensitive client identifiers if obfuscation is preferred.
    
    Structured Data:
    {json.dumps(structured_data, indent=2)}
    
    JSON Output:
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:-3].strip()
        elif text.startswith("```"):
            text = text[3:-3].strip()
        return json.loads(text)
    except Exception as e:
        logger.error(f"Error generating JD formats with Gemini: {e}")
        return {
            "internal": f"# {structured_data.get('title')}\nDetails extraction failed.",
            "short": f"Role: {structured_data.get('title')}",
            "candidate": f"# {structured_data.get('title')}\nExciting opportunity."
        }

def generate_embedding(text: str) -> List[float]:
    """
    Generates a 384-dimensional dense vector using local sentence-transformers (all-MiniLM-L6-v2).
    """
    try:
        if embedding_model is None:
            raise Exception("Embedding model not initialized.")
        
        # Explicitly encode to numpy then convert to list
        embedding = embedding_model.encode(text)
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Error generating local embedding: {e}")
        # Fallback to zero vector if failed
        return [0.0] * 384

def extract_resume_metadata(raw_text: str) -> dict:
    """
    Uses Gemini 2.5 Pro to extract structured metadata from a resume with a regex fallback.
    """
    model = genai.GenerativeModel('gemini-2.5-pro')
    
    prompt = f"""
    You are a high-fidelity resume parsing engine. Extract structured data from the resume text provided below.
    
    CRITICAL: Return ONLY a valid JSON object. No other text.
    
    JSON Schema:
    {{
      "name": "Full Name",
      "email": "email@example.com or null",
      "phone": "phone number or null",
      "skills": ["Skill1", "Skill2", ...],
      "experience_years": integer,
      "location": "City, Country or null"
    }}
    
    Instructions:
    - name: Look for the largest text at the top or prominent name in the header.
    - email: Extract the primary email.
    - skills: List all technical and professional skills found.
    - experience_years: Calculate total years of professional experience as an integer.
    
    Resume Text:
    ---
    {raw_text[:10000]}
    ---
    
    JSON Output:
    """
    
    import re
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', raw_text)
    phone_match = re.search(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', raw_text)
    
    extracted_data = {
        "name": "Unknown",
        "email": email_match.group(0) if email_match else None,
        "phone": phone_match.group(0) if phone_match else None,
        "skills": [],
        "experience_years": 0,
        "location": "Not specified"
    }

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
            
        ai_data = json.loads(text)
        
        for key in extracted_data:
            if ai_data.get(key) and ai_data[key] not in ["Unknown", "Not specified", "null", None]:
                extracted_data[key] = ai_data[key]
        
        exp = extracted_data.get("experience_years", 0)
        if isinstance(exp, str):
            digits = re.findall(r'\d+', exp)
            extracted_data["experience_years"] = int(digits[0]) if digits else 0
        else:
            extracted_data["experience_years"] = int(exp) if exp else 0
            
    except Exception as e:
        logger.error(f"Gemini parsing failed, using regex fallback: {e}")
        
    return extracted_data
