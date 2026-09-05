import os
import httpx
from google import genai

async def dispatch_gemini_slack_alert(intent: str, status: str, rigs_score: str):
    slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    # Real Gemini API live call
    client = genai.Client(api_key=gemini_key)
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=f"Perform an immediate live executive RevOps risk and growth assessment for SparkleNET pipeline event: Intent '{intent}' with RIGS score '{rigs_score}'."
    )
    reasoning_output = response.text.strip()

    payload = {
        "text": f"🚀 *SparkleNET Live RevOps Intelligence Bus*\n> *Intent:* {intent}\n> *RIGS Score:* {rigs_score}\n> *Gemini Live Reasoning:* {reasoning_output}\n> *Status:* {status}"
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(slack_webhook, json=payload)
