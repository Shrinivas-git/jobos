import logging
from utils.gemini_utils import _call_groq, GROQ_REASON_MODEL

logger = logging.getLogger(__name__)


def generate_rejection_feedback(jd_structured: dict, gaps: list, candidate_profile: dict) -> str:
    """Uses Groq (reason model) to generate 3-5 sentence constructive feedback for a rejected candidate."""
    jd_title = jd_structured.get("title", "this role")
    jd_level = jd_structured.get("level", "")
    jd_skills = jd_structured.get("skills", [])
    jd_exp = jd_structured.get("relevant_experience", 0)

    candidate_exp = candidate_profile.get("experience_years", 0)
    candidate_skills = candidate_profile.get("skills", [])

    gaps_text = "\n".join(f"- {g}" for g in gaps) if gaps else "- No specific gaps recorded"

    prompt = f"""You are a compassionate and professional career advisor writing feedback to a candidate who was not selected for a role.

JOB DETAILS:
- Title: {jd_title} ({jd_level})
- Required skills: {', '.join(jd_skills[:10]) if jd_skills else 'Not specified'}
- Required experience: {jd_exp} years

CANDIDATE PROFILE:
- Experience: {candidate_exp} years
- Skills: {', '.join(candidate_skills[:10]) if candidate_skills else 'Not specified'}

EVALUATION GAPS (reasons the candidate was not selected):
{gaps_text}

Write 3-5 sentences of constructive, encouraging feedback for this candidate.
Rules:
- Frame each gap as a specific actionable improvement (e.g. "consider gaining experience in X by doing Y")
- Do NOT say "you were rejected" or use negative language
- Be specific to the role requirements — do not give generic advice
- End with an encouraging note about their overall profile
- Return ONLY the feedback paragraph, no JSON, no headers, no bullet points

FEEDBACK:"""

    try:
        return _call_groq(GROQ_REASON_MODEL, prompt, max_tokens=512)
    except Exception as e:
        logger.error(f"Feedback generation failed: {e}")
        return (
            f"Thank you for your interest in the {jd_title} position. "
            "While we appreciated reviewing your profile, we are moving forward with candidates whose experience "
            "more closely matches our current requirements. We encourage you to continue developing your skills "
            "and welcome you to apply for future opportunities."
        )
