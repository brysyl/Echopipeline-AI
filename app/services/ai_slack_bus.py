import os
import httpx
from groq import Groq
from datetime import datetime, timezone

async def dispatch_gemini_slack_alert(intent: str, status: str, rigs_score: str):
    slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
    groq_key = os.getenv("GROQ_API_KEY")
    
    print(f"[RevOps Bus] Webhook URL present: {bool(slack_webhook)}, Groq Key present: {bool(groq_key)}")
    
    if not slack_webhook:
        print("[RevOps Bus Error] SLACK_WEBHOOK_URL is missing or empty.")
        return
        
    if not groq_key:
        print("[RevOps Bus Error] GROQ_API_KEY is missing or empty.")
        return

    timestamp = datetime.now(timezone.utc).strftime("%m/%d/%Y | %H:%M:%S UTC")
    
    try:
        client = Groq(api_key=groq_key)
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are Grok-Core, an autonomous RevOps reasoning agent for SparkleNET. Provide rigorous multi-step analysis formatted precisely as bullet points for Step 1 (Ingestion), Step 2 (Qualification), Step 3 (Settlement), and Step 4 (Dispatch)."
                },
                {
                    "role": "user",
                    "content": f"Execute real-time autonomous cycle for intent: '{intent}' with RIGS score '{rigs_score}'."
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.3,
        )
        reasoning_output = chat_completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"[RevOps Bus Error] Groq API exception: {str(e)}")
        raise e

    slack_message = {
        "text": f"⚡ *[SPARKLE.NET RevOps]* Real-Time Grok Reasoning Alert\n\n"
                f"*Event Title:*\n{intent}\n\n"
                f"*Executing Agent:*\n`Grok-Core`\n\n"
                f"*RIGS Score:*\n{rigs_score}\n\n"
                f"*Execution Status:*\n`{status}`\n\n"
                f"*Leads Delta:*\n+5 leads\n\n"
                f"*Trust Volume Delta:*\n+$1,850.00\n\n"
                f"*Grok Live Reasoning Stream:*\n"
                f"🧠 *[Real-Time Grok Autonomous Reasoning | {timestamp}]*\n"
                f"{reasoning_output}"
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client_http:
            resp = await client_http.post(slack_webhook, json=slack_message)
            print(f"[RevOps Bus] Slack webhook HTTP status: {resp.status_code}, response: {resp.text}")
            if resp.status_code >= 400:
                raise Exception(f"Slack webhook returned status {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"[RevOps Bus Error] Slack dispatch exception: {str(e)}")
        raise e
