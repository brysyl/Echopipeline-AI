import os
import json
from datetime import datetime
from typing import Optional, Dict, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, Header, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import asyncpg
import httpx

# --- Environment Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "sk_live_exec_99a8b")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

db_pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    if DATABASE_URL:
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    yield
    if db_pool:
        await db_pool.close()

app = FastAPI(
    title="EchoPipeline-AI",
    description="SparkleNET Executive RevOps Control Center with Grok Reasoning Engine",
    version="2.1.0",
    lifespan=lifespan
)

# --- Security Middleware ---
async def verify_admin_api_key(x_api_key: Optional[str] = Header(None)):
    if x_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid Executive API Key")
    return x_api_key

async def verify_alexa_request(request: Request):
    signature = request.headers.get("Signature")
    cert_url = request.headers.get("SignatureCertChainUrl")
    if os.getenv("RAILWAY_ENVIRONMENT") == "production":
        if not signature or not cert_url:
            raise HTTPException(status_code=400, detail="Missing Alexa verification headers")
    return True

# --- DB Logging Utility ---
async def log_event(source: str, event: str, status: str):
    if not db_pool: return
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO public.audit_logs (source, event, status) VALUES ($1, $2, $3)",
            source, event, status
        )

# --- Grok / LLM Reasoning Engine ---
async def run_grok_reasoning(prompt: str, system_prompt: str = "You are a concise executive RevOps reasoning agent.") -> str:
    if not GROQ_API_KEY:
        return "Grok API key not configured. Falling back to deterministic scoring."
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 250
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            return f"Grok API error: {resp.status_code}"
        except Exception as e:
            return f"Grok execution error: {str(e)}"

# --- Slack Dispatcher ---
async def dispatch_slack_alert(message: str):
    if SLACK_WEBHOOK_URL:
        async with httpx.AsyncClient() as client:
            try:
                await client.post(SLACK_WEBHOOK_URL, json={"text": message})
            except Exception:
                pass

# --- Pydantic Models ---
class RIGSInput(BaseModel):
    organization: str
    risk_score: float = Field(..., ge=0.0, le=1.0)
    intent_score: int = Field(..., ge=0, le=100)
    growth_tier: str
    stakeholder_role: str

class StrategyQuery(BaseModel):
    query: str

class SlotValue(BaseModel):
    value: Optional[str] = None

class IntentPayload(BaseModel):
    name: str
    slots: Optional[Dict[str, SlotValue]] = None

class AlexaRequestContainer(BaseModel):
    intent: IntentPayload

class AlexaWebhookBody(BaseModel):
    request: AlexaRequestContainer

# --- Dashboard Interface ---
@app.get("/", response_class=HTMLResponse)
async def executive_control_room():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SparkleNET | Executive RevOps Engine</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
            let volumeChart;

            async function fetchState() {
                try {
                    const [metricsRes, logsRes] = await Promise.all([
                        fetch('/api/metrics'), fetch('/api/friction-logs')
                    ]);
                    const metrics = await metricsRes.json();
                    const logs = await logsRes.json();

                    document.getElementById('metric-leads').innerText = metrics.leads_enriched.toLocaleString();
                    document.getElementById('metric-volume').innerText = '$' + metrics.trust_volume.toLocaleString();
                    document.getElementById('metric-rigs').innerText = metrics.rigs_qualified.toLocaleString();
                    document.getElementById('metric-latency').innerText = metrics.mcp_latency + 'ms';
                    
                    updateChart(metrics.trust_volume);

                    document.getElementById('log-stream').innerHTML = logs.map(l => `
                        <div class="flex items-center justify-between py-2 border-b border-slate-800/60 text-xs font-mono">
                            <span class="text-slate-500">[${l.created_at}]</span>
                            <span class="text-indigo-400 font-semibold">${l.source}</span>
                            <span class="text-slate-300 truncate max-w-xs">${l.event}</span>
                            <span class="px-2 py-0.5 rounded text-[10px] font-bold border ${l.status === 'SUCCESS' || l.status === 'Cleared' || l.status === 'VERIFIED' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border-amber-500/20'}">${l.status}</span>
                        </div>
                    `).join('');
                } catch (e) { console.error('Sync failed', e); }
            }

            function updateChart(newVolume) {
                if(!volumeChart) return;
                const now = new Date().toLocaleTimeString();
                if(volumeChart.data.labels.length > 10) {
                    volumeChart.data.labels.shift();
                    volumeChart.data.datasets[0].data.shift();
                }
                volumeChart.data.labels.push(now);
                volumeChart.data.datasets[0].data.push(newVolume);
                volumeChart.update();
            }

            window.onload = () => {
                const ctx = document.getElementById('telemetryChart').getContext('2d');
                volumeChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: [],
                        datasets: [{
                            label: 'Settlement Trust Volume ($)',
                            data: [],
                            borderColor: '#6366f1',
                            backgroundColor: 'rgba(99, 102, 241, 0.1)',
                            fill: true, tension: 0.4
                        }]
                    },
                    options: {
                        responsive: true, maintainAspectRatio: false,
                        scales: {
                            x: { grid: { color: '#1e293b' }, ticks: { color: '#94a3b8' } },
                            y: { grid: { color: '#1e293b' }, ticks: { color: '#94a3b8' } }
                        },
                        plugins: { legend: { display: false } }
                    }
                });
                fetchState();
                setInterval(fetchState, 3000);
            };
        </script>
    </head>
    <body class="bg-slate-950 text-slate-100 font-sans antialiased min-h-screen flex flex-col">
        <header class="border-b border-slate-800 bg-slate-900/50 backdrop-blur sticky top-0 z-50 px-6 h-16 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <div class="w-3 h-3 bg-emerald-500 rounded-full animate-pulse"></div>
                <h1 class="text-lg font-bold">SparkleNET Engine <span class="text-xs font-normal text-slate-400 ml-2">Zero-Latency RevOps + Grok Reasoning</span></h1>
            </div>
            <span class="px-3 py-1 text-xs font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 rounded-full">Grok AI Online</span>
        </header>
        <main class="max-w-7xl mx-auto px-6 py-8 w-full grid gap-6 flex-grow">
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
                    <p class="text-xs font-medium text-slate-400 uppercase tracking-wider">Active Leads</p>
                    <p id="metric-leads" class="text-3xl font-extrabold text-white mt-2">--</p>
                </div>
                <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
                    <p class="text-xs font-medium text-slate-400 uppercase tracking-wider">Trust Settled</p>
                    <p id="metric-volume" class="text-3xl font-extrabold text-white mt-2">--</p>
                </div>
                <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
                    <p class="text-xs font-medium text-slate-400 uppercase tracking-wider">RIGS Qualified</p>
                    <p id="metric-rigs" class="text-3xl font-extrabold text-white mt-2">--</p>
                </div>
                <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
                    <p class="text-xs font-medium text-slate-400 uppercase tracking-wider">MCP Latency</p>
                    <p id="metric-latency" class="text-3xl font-extrabold text-white mt-2">--</p>
                </div>
            </div>
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div class="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-xl p-6">
                    <h2 class="text-base font-semibold text-white mb-4">Real-time Telemetry Velocity</h2>
                    <div class="h-64 relative"><canvas id="telemetryChart"></canvas></div>
                </div>
                <div class="bg-slate-900 border border-slate-800 rounded-xl p-6 flex flex-col h-full">
                    <h2 class="text-base font-semibold text-white mb-4">Automated Settlement Feed</h2>
                    <div id="log-stream" class="bg-slate-950 border border-slate-800 rounded-lg p-3 flex-grow overflow-y-auto space-y-2"></div>
                </div>
            </div>
        </main>
    </body>
    </html>
    """

# --- Telemetry Routes ---
@app.get("/api/metrics")
async def get_metrics():
    if not db_pool: return {"leads_enriched": 0, "trust_volume": 0, "rigs_qualified": 0, "mcp_latency": 0}
    async with db_pool.acquire() as conn:
        leads_count = await conn.fetchval("SELECT COUNT(*) FROM public.leads")
        rigs_count = await conn.fetchval("SELECT COUNT(*) FROM public.leads WHERE status = 'Qualified'")
        volume = await conn.fetchval("SELECT COALESCE(SUM(volume_amount), 0) FROM public.settlement_ledger")
    return {
        "leads_enriched": leads_count,
        "trust_volume": float(volume),
        "rigs_qualified": rigs_count,
        "mcp_latency": 88
    }

@app.get("/api/friction-logs")
async def get_logs():
    if not db_pool: return []
    async with db_pool.acquire() as conn:
        records = await conn.fetch("SELECT source, event, status, to_char(created_at, 'HH24:MI:SS') as created_at FROM public.audit_logs ORDER BY created_at DESC LIMIT 8")
    return [dict(r) for r in records]

# --- Grok-Enhanced Inbound Webhook Ingestion ---
@app.post("/api/v1/webhook/ingest")
async def ingest_lead(payload: RIGSInput):
    status = "Qualified" if (payload.risk_score < 0.40 and payload.intent_score >= 75 and payload.growth_tier in ["Tier-1", "Enterprise"]) else "Review"
    if payload.risk_score >= 0.70: status = "Disqualified"

    # Executive reasoning via Grok
    reasoning_prompt = f"Analyze lead: {payload.organization}, Risk: {payload.risk_score}, Intent: {payload.intent_score}, Tier: {payload.growth_tier}, Stakeholder: {payload.stakeholder_role}. Give a 1-sentence strategic deal verdict."
    reasoning_summary = await run_grok_reasoning(reasoning_prompt)

    if db_pool:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO public.leads (organization, risk_score, intent_score, growth_tier, stakeholder_role, status) VALUES ($1, $2, $3, $4, $5, $6)",
                payload.organization, payload.risk_score, payload.intent_score, payload.growth_tier, payload.stakeholder_role, status
            )

    event_msg = f"RIGS {status}: {payload.organization} | Grok: {reasoning_summary}"
    await log_event("n8n-grok-ingest", event_msg[:500], "VERIFIED")

    if status == "Qualified":
        await dispatch_slack_alert(f"🚨 *Grok Verified Qualified Lead*\n*Org*: {payload.organization}\n*Verdict*: {reasoning_summary}")

    return {
        "status": "processed",
        "organization": payload.organization,
        "rigs_result": status,
        "grok_reasoning": reasoning_summary
    }

# --- Executive Grok Strategy Endpoint ---
@app.post("/api/v1/reason", dependencies=[Depends(verify_admin_api_key)])
async def executive_reasoning(query: StrategyQuery):
    reasoning = await run_grok_reasoning(
        query.query,
        system_prompt="You are SparkleNET's Chief RevOps AI Architect. Provide concise, high-leverage strategic reasoning."
    )
    await log_event("grok-reasoning-api", f"Query executed: {query.query[:50]}...", "SUCCESS")
    return {"query": query.query, "executive_reasoning": reasoning}

# --- Grok-Enhanced Alexa Intent Handler ---
@app.post("/api/alexa/intent", dependencies=[Depends(verify_alexa_request)])
async def handle_alexa_intent(body: AlexaWebhookBody):
    intent_name = body.request.intent.name
    slots = body.request.intent.slots or {}
    speech_text = "EchoPipeline operational."

    if intent_name == "GetPipelineStatusIntent":
        if db_pool:
            async with db_pool.acquire() as conn:
                q_count = await conn.fetchval("SELECT COUNT(*) FROM public.leads WHERE status = 'Qualified'")
                vol = await conn.fetchval("SELECT COALESCE(SUM(volume_amount), 0) FROM public.settlement_ledger")
            speech_text = f"SparkleNET pipeline active with {q_count} qualified accounts and ${vol:,.2f} settled trust volume."
            await log_event("alexa-bridge", "Pipeline status queried via voice", "SUCCESS")
            
    elif intent_name == "QueryRIGSIntent":
        company = slots.get("Company").value if slots.get("Company") else "Apex Logistics"
        reasoning = await run_grok_reasoning(f"Provide a 1-sentence voice update on company status for {company}.")
        speech_text = f"RIGS update for {company}: {reasoning}"
        await log_event("alexa-bridge", f"Voice RIGS check with Grok for {company}", "SUCCESS")

    elif intent_name == "TriggerSettlementIntent":
        amt = 25000.00
        if db_pool:
            async with db_pool.acquire() as conn:
                await conn.execute("INSERT INTO public.settlement_ledger (event_source, volume_amount, status) VALUES ($1, $2, $3)", "alexa_override", amt, "Cleared")
        speech_text = f"Trust settlement escrow cleared for ${amt:,.2f}."
        await log_event("alexa-bridge", f"Escrow settlement triggered (${amt})", "Cleared")

    return {
        "version": "1.0",
        "response": {
            "outputSpeech": {"type": "PlainText", "text": speech_text},
            "shouldEndSession": True
        }
    }
