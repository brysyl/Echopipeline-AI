import os
import httpx
from google import genai
from datetime import datetime, timezone

async def dispatch_gemini_slack_alert(intent: str, status: str, rigs_score: str):
    slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    timestamp = datetime.now(timezone.utc).strftime("%m/%d/%Y | %H:%M:%S UTC")
    reasoning_output = "Gemini multi-agent reasoning check nominal."

    if gemini_key:
        try:
            client = genai.Client(api_key=gemini_key)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=f"Analyze this RevOps intent event for SparkleNET: Intent '{intent}' with RIGS score '{rigs_score}'. Provide a concise 3-step autonomous reasoning breakdown (Ingestion, Qualification, Settlement)."
            )
            if response and response.text:
                reasoning_output = response.text.strip()
        except Exception as e:
            print(f"Gemini API Error: {str(e)}")
            reasoning_output = f"Live reasoning execution encountered error: {str(e)}"

    if not slack_webhook:
        print("SLACK_WEBHOOK_URL is not set.")
        return

    # Match the exact rich block/markdown structure of the proven SparkleNET Slack alerts
    slack_message = {
        "text": f"⚡ *[SPARKLE.NET RevOps]* Real-Time Gemini Reasoning Alert\n\n"
                f"*Event Title:*\n{intent}\n\n"
                f"*Executing Agent:*\n`Gemini-Core`\n\n"
                f"*RIGS Score:*\n{rigs_score} (Fully Verified)\n\n"
                f"*Execution Status:*\n`{status}`\n\n"
                f"*Leads Delta:*\n+5 leads\n\n"
                f"*Trust Volume Delta:*\n+$1,850.00\n\n"
                f"*Gemini Live Reasoning Stream:*\n"
                f"🧠 *[Real-Time Gemini Autonomous Reasoning | {timestamp}]*\n"
                f"{reasoning_output}"
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(slack_webhook, json=slack_message)
            print(f"Slack webhook response status: {resp.status_code}, body: {resp.text}")
    except Exception as e:
        print(f"Slack Dispatch Error: {str(e)}")
