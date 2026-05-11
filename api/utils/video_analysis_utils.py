import os
import logging
import subprocess
import json
import tempfile

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

try:
    import cv2
    import numpy as np
    import mediapipe as mp
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False
    logger.warning("cv2/mediapipe not installed")

try:
    from groq import Groq
    GROQ_AVAILABLE = bool(GROQ_API_KEY)
    _groq = Groq(api_key=GROQ_API_KEY) if GROQ_AVAILABLE else None
except ImportError:
    GROQ_AVAILABLE = False
    _groq = None
    logger.warning("groq not installed")


def _extract_audio(video_path: str) -> str | None:
    """Extract audio from video using ffmpeg. Returns temp wav file path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-vn", "-ar", "16000", "-ac", "1", "-f", "wav", tmp.name],
            capture_output=True, timeout=120
        )
        if result.returncode == 0 and os.path.getsize(tmp.name) > 0:
            return tmp.name
        logger.error(f"ffmpeg failed: {result.stderr.decode()}")
        return None
    except Exception as e:
        logger.error(f"Audio extraction failed: {e}")
        return None


def _transcribe_audio(audio_path: str) -> str:
    """Transcribe audio using Groq Whisper."""
    if not GROQ_AVAILABLE:
        return ""
    try:
        with open(audio_path, "rb") as f:
            response = _groq.audio.transcriptions.create(
                file=("audio.wav", f, "audio/wav"),
                model="whisper-large-v3",
                language="en"
            )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return ""


def _analyze_speech(transcript: str) -> dict:
    """Use Groq LLM to analyze speaking skills from transcript."""
    if not GROQ_AVAILABLE or not transcript:
        return {
            "articulation_score": 6,
            "speaking_pace": "normal",
            "filler_words": 0,
            "speech_traits": [],
            "speech_impression": "Speech analysis unavailable."
        }
    try:
        prompt = f"""Analyze this video resume transcript for speaking skills. Return ONLY valid JSON, no extra text.

Transcript:
\"\"\"{transcript}\"\"\"

Return:
{{
  "articulation_score": <1-10, clarity and vocabulary quality>,
  "speaking_pace": "<slow|normal|fast>",
  "filler_words": <count of um/uh/like/you know>,
  "speech_traits": ["<trait1>", "<trait2>"],
  "speech_impression": "<1-2 sentences on communication style>"
}}

Score 7 = average, 9-10 = exceptional. speech_traits examples: fluent, articulate, well-structured, confident-speaker, hesitant, uses-fillers, monotone, engaging."""

        response = _groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=300
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        logger.error(f"Speech analysis failed: {e}")
        return {
            "articulation_score": 6,
            "speaking_pace": "normal",
            "filler_words": 0,
            "speech_traits": [],
            "speech_impression": "Speech analysis failed."
        }


def _analyze_visuals(video_path: str) -> dict:
    """Analyze posture and eye contact using OpenCV + MediaPipe."""
    default = {"confidence_score": 6, "eye_contact_score": 6, "video_quality": "unknown", "duration": 0}

    if not VISION_AVAILABLE:
        return default

    try:
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps

        mp_pose = mp.solutions.pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
        mp_face = mp.solutions.face_detection.FaceDetection(min_detection_confidence=0.5)

        posture_scores = []
        eye_scores = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_idx += 1
            if frame_idx % 15 != 0:  # sample every 15th frame
                continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            pose_result = mp_pose.process(rgb)
            if pose_result.pose_landmarks:
                lm = pose_result.pose_landmarks.landmark
                # Shoulder alignment
                shoulder_diff = abs(lm[11].x - lm[12].x)
                hip_offset = abs((lm[11].x + lm[12].x) / 2 - (lm[23].x + lm[24].x) / 2)
                posture = max(1, min(10, 9 - hip_offset * 15))
                posture_scores.append(posture)

            face_result = mp_face.process(rgb)
            if face_result.detections:
                detection = face_result.detections[0]
                bbox = detection.location_data.relative_bounding_box
                # Face centered = looking at camera
                center_x = bbox.xmin + bbox.width / 2
                offset = abs(center_x - 0.5)
                eye_score = max(1, min(10, 9 - offset * 12))
                eye_scores.append(eye_score)

        cap.release()
        mp_pose.close()
        mp_face.close()

        confidence = round(float(np.mean(posture_scores))) if posture_scores else 6
        eye_contact = round(float(np.mean(eye_scores))) if eye_scores else 6

        # Video quality from frame count
        quality = "good" if total_frames > 300 else "low"

        return {
            "confidence_score": max(1, min(10, confidence)),
            "eye_contact_score": max(1, min(10, eye_contact)),
            "video_quality": quality,
            "duration": round(duration, 1)
        }
    except Exception as e:
        logger.error(f"Visual analysis failed: {e}")
        return default


def _generate_overall_impression(visual: dict, speech: dict, transcript: str) -> str:
    """Use Groq to write a cohesive overall impression combining all signals."""
    if not GROQ_AVAILABLE:
        return f"Candidate shows {visual.get('confidence_score', 6)}/10 confidence and {speech.get('articulation_score', 6)}/10 articulation."
    try:
        prompt = f"""Write a 2-3 sentence professional HR assessment of this candidate based on their video resume analysis.

Visual scores: Confidence {visual['confidence_score']}/10, Eye Contact {visual['eye_contact_score']}/10
Speech scores: Articulation {speech['articulation_score']}/10, Pace {speech['speaking_pace']}, Filler words {speech['filler_words']}
Speech traits: {', '.join(speech.get('speech_traits', []))}
Transcript excerpt: \"{transcript[:300]}\"

Be honest and specific. Write as a talent scout would."""

        response = _groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Impression generation failed: {e}")
        return speech.get("speech_impression", "Analysis complete.")


def analyze_video_resume(video_path: str) -> dict:
    """
    Full video resume analysis:
    - Visual: OpenCV + MediaPipe (posture/eye contact)
    - Speech: Groq Whisper (transcription) + Groq LLM (speaking skills)
    """
    if not os.path.exists(video_path):
        logger.error(f"Video not found: {video_path}")
        return {
            "confidence_score": 0, "articulation_score": 0,
            "eye_contact_score": 0, "professionalism_score": 0,
            "speaking_pace": "unknown", "engagement_level": "unknown",
            "overall_impression": "Video file not found.", "traits": [], "duration": 0
        }

    logger.info(f"Starting full video analysis: {video_path}")

    # Step 1: Visual analysis
    visual = _analyze_visuals(video_path)
    logger.info(f"Visual: confidence={visual['confidence_score']}, eye={visual['eye_contact_score']}")

    # Step 2: Extract audio and transcribe
    transcript = ""
    speech = {"articulation_score": 6, "speaking_pace": "normal", "filler_words": 0, "speech_traits": [], "speech_impression": ""}
    audio_path = _extract_audio(video_path)
    if audio_path:
        try:
            transcript = _transcribe_audio(audio_path)
            logger.info(f"Transcript ({len(transcript)} chars): {transcript[:100]}...")
            if transcript:
                speech = _analyze_speech(transcript)
                logger.info(f"Speech: articulation={speech['articulation_score']}, pace={speech['speaking_pace']}")
        finally:
            try:
                os.unlink(audio_path)
            except Exception:
                pass

    # Step 3: Overall impression
    overall = _generate_overall_impression(visual, speech, transcript)

    # Step 4: Combine traits
    traits = []
    if visual["confidence_score"] >= 7:
        traits.append("confident")
    if visual["eye_contact_score"] >= 7:
        traits.append("engaged")
    if speech["articulation_score"] >= 7:
        traits.append("articulate")
    if speech["filler_words"] <= 3:
        traits.append("fluent")
    elif speech["filler_words"] >= 8:
        traits.append("uses-fillers")
    traits += speech.get("speech_traits", [])
    traits = list(dict.fromkeys(traits))[:5]  # dedupe, max 5

    professionalism = round((visual["confidence_score"] + speech["articulation_score"]) / 2)
    engagement = "high" if visual["eye_contact_score"] >= 7 else "medium" if visual["eye_contact_score"] >= 5 else "low"

    return {
        "confidence_score": visual["confidence_score"],
        "articulation_score": speech["articulation_score"],
        "eye_contact_score": visual["eye_contact_score"],
        "professionalism_score": max(1, min(10, professionalism)),
        "speaking_pace": speech["speaking_pace"],
        "filler_words": speech["filler_words"],
        "engagement_level": engagement,
        "overall_impression": overall,
        "traits": traits if traits else ["professional"],
        "duration": visual["duration"],
        "video_quality": visual["video_quality"],
        "transcript": transcript[:500] if transcript else None
    }
