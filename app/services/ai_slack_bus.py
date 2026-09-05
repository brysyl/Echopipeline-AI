import os
import httpx
from google import genai

async def dispatch_gemini_slack_alert(intent: str, status: str, rigs_score: str):
    slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    reasoning_output = "Gemini multi-agent reasoning check nominal."
    if gemini_key:
        try:
            client = genai.Client(api_key=gemini_key)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=f"Analyze this RevOps intent event for SparkleNET: Intent '{intent}' with RIGS score '{rigs_score}'. Provide a 1-sentence executive risk and growth assessment."
            )
            if response and response.text:
                reasoning_output = response.text.strip()
        except Exception as e:
            reasoning_output = f"Reasoning Fallback Engaged: {str(e)}"

    if not slack_webhook:
        return

    payload = {
        "text": f"🚀 *SparkleNET RevOps Intelligence Bus*\n> *Intent:* {intent}\n> *RIGS Score:* {rigs_score}\n> *Gemini Analysis:* {reasoning_output}\n> *Status:* {status}"
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            await client.post(slack_webhook, json=payload)
    except Exception as e:
        print(f"Slack Dispatch Error: {str(e)}")
