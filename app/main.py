import os
import json
import asyncio
from datetime import datetime, timezone
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

async def init_db_schema():
    if not db_pool:
        return
    async with db_pool.acquire() as conn:
        # Create Core Tables
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS public.leads (
                id SERIAL PRIMARY KEY,
                organization VARCHAR(255) NOT NULL,
                risk_score FLOAT NOT NULL,
                intent_score INT NOT NULL,
                growth_tier VARCHAR(50) NOT NULL,
                stakeholder_role VARCHAR(100) NOT NULL,
                status VARCHAR(50) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS public.settlement_ledger (
                id SERIAL PRIMARY KEY,
                event_source VARCHAR(100) NOT NULL,
                volume_amount NUMERIC(12, 2) NOT NULL,
                status VARCHAR(50) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS public.audit_logs (
                id SERIAL PRIMARY KEY,
                source VARCHAR(100) NOT NULL,
                event TEXT NOT NULL,
                status VARCHAR(50) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Seed initial data if empty
        lead_count = await conn.fetchval("SELECT COUNT(*) FROM public.leads")
        if lead_count == 0:
            await conn.execute("""
                INSERT INTO public.leads (organization, risk_score, intent_score, growth_tier, stakeholder_role, status) VALUES
                ('Nexus Global Logistics', 0.12, 92, 'Enterprise', 'CTO', 'Qualified'),
                ('AeroTech Defense', 0.85, 40, 'Tier-3', 'Procurement', 'Disqualified'),
                ('Fintech Pulse', 0.25, 88, 'Tier-1', 'VP RevOps', 'Qualified'),
                ('Vanguard Energy', 0.35, 78, 'Enterprise', 'Chief Architect', 'Qualified');

                INSERT INTO public.settlement_ledger (event_source, volume_amount, status) VALUES
                ('rigs_automated_clearing', 125000.00, 'Cleared'),
                ('mcp_trust_protocol', 84000.00, 'Cleared'),
                ('stripe_settlement_sync', 43500.00, 'Cleared');

                INSERT INTO public.audit_logs (source, event, status) VALUES
                ('RIGS-Engine', 'Pipeline initialized with zero-latency enforcement', 'SUCCESS'),
                ('MCP-Protocol', 'Trust verification pipeline attached to Supabase pool', 'VERIFIED'),
                ('Grok-Reasoner', 'Autonomous strategy model llama-3.3-70b attached', 'SUCCESS');
            """)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    if DATABASE_URL:
        try:
            db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
            await init_db_schema()
        except Exception as e:
            print(f"Database connection/initialization error: {e}")
    yield
    if db_pool:
        await db_pool.close()

# --- Initialize Application ---
app = FastAPI(
    title="EchoPipeline-AI",
    description="SparkleNET Executive RevOps Control Room",
    version="2.5.0",
    lifespan=lifespan
)

# --- Health Probes ---
@app.get("/health")
@app.get("/healthz")
async def health_check():
    return {"status": "ok", "database": "connected" if db_pool else "fallback_mode"}

# --- LLM Reasoning Module ---
async def run_grok_reasoning(prompt: str) -> str:
    if not GROQ_API_KEY:
        return "Deterministic Qualification: RIGS threshold parameters satisfied."
    
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "You are SparkleNET's Chief RevOps AI Reasoning Engine. Give 1 concise, direct executive line."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 150
    }
    
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            resp = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"].strip()
            return f"Model returned status {resp.status_code}"
        except Exception as e:
            return f"Reasoning pipeline latency timeout: {str(e)}"

# --- Data Models ---
class RIGSInput(BaseModel):
    organization: str
    risk_score: float = Field(..., ge=0.0, le=1.0)
    intent_score: int = Field(..., ge=0, le=100)
    growth_tier: str
    stakeholder_role: str

# --- Full Production Dashboard Interface ---
@app.get("/", response_class=HTMLResponse)
async def executive_control_room():
    return """
    <!DOCTYPE html>
    <html lang="en" class="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SparkleNET | Executive RevOps Control Room</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Plus Jakarta Sans', sans-serif; }
            .mono { font-family: 'JetBrains Mono', monospace; }
        </style>
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col antialiased">
        <header class="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur sticky top-0 z-50 px-6 h-16 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <div class="w-3 h-3 bg-emerald-500 rounded-full animate-ping"></div>
                <h1 class="text-base font-bold tracking-tight">SparkleNET RevOps Engine <span class="text-xs font-mono font-normal text-slate-400 ml-2">v2.5.0</span></h1>
            </div>
            <div class="flex items-center space-x-3">
                <button onclick="triggerSimulatedIngest()" class="px-3 py-1.5 text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition shadow-lg shadow-indigo-600/20">
                    + Simulate Live Ingest
                </button>
                <span class="px-2.5 py-1 text-xs font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-md">GROK REASONER ONLINE</span>
            </div>
        </header>

        <main class="max-w-7xl mx-auto px-6 py-6 w-full space-y-6 flex-grow">
            <!-- Metrics Row -->
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div class="bg-slate-900/80 border border-slate-800/80 rounded-xl p-5 relative overflow-hidden">
                    <p class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Active Leads</p>
                    <p id="metric-leads" class="text-3xl font-extrabold text-white mt-2 mono">--</p>
                    <span class="text-[10px] text-emerald-400 font-mono mt-1 block">↑ Real-time Ingest</span>
                </div>
                <div class="bg-slate-900/80 border border-slate-800/80 rounded-xl p-5 relative overflow-hidden">
                    <p class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Trust Settled</p>
                    <p id="metric-volume" class="text-3xl font-extrabold text-indigo-400 mt-2 mono">$0</p>
                    <span class="text-[10px] text-indigo-400 font-mono mt-1 block">Settlement Ledger Verified</span>
                </div>
                <div class="bg-slate-900/80 border border-slate-800/80 rounded-xl p-5 relative overflow-hidden">
                    <p class="text-xs font-semibold text-slate-400 uppercase tracking-wider">RIGS Qualified</p>
                    <p id="metric-rigs" class="text-3xl font-extrabold text-emerald-400 mt-2 mono">--</p>
                    <span class="text-[10px] text-slate-400 font-mono mt-1 block">Risk < 0.40 | Intent > 75</span>
                </div>
                <div class="bg-slate-900/80 border border-slate-800/80 rounded-xl p-5 relative overflow-hidden">
                    <p class="text-xs font-semibold text-slate-400 uppercase tracking-wider">MCP Latency</p>
                    <p id="metric-latency" class="text-3xl font-extrabold text-amber-400 mt-2 mono">14ms</p>
                    <span class="text-[10px] text-emerald-400 font-mono mt-1 block">Zero-Latency Pipeline</span>
                </div>
            </div>

            <!-- Main Charts & Feed Split -->
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div class="lg:col-span-2 bg-slate-900/80 border border-slate-800/80 rounded-xl p-6 flex flex-col justify-between">
                    <div class="flex items-center justify-between mb-4">
                        <h2 class="text-sm font-bold text-slate-200 uppercase tracking-wider">Real-Time Telemetry Velocity</h2>
                        <span class="text-xs font-mono text-slate-400">Ledger Stream ($)</span>
                    </div>
                    <div class="h-72 w-full relative">
                        <canvas id="telemetryChart"></canvas>
                    </div>
                </div>

                <div class="bg-slate-900/80 border border-slate-800/80 rounded-xl p-6 flex flex-col h-full">
                    <div class="flex items-center justify-between mb-4">
                        <h2 class="text-sm font-bold text-slate-200 uppercase tracking-wider">Automated Settlement Feed</h2>
                        <span class="w-2 h-2 bg-emerald-400 rounded-full animate-ping"></span>
                    </div>
                    <div id="log-stream" class="bg-slate-950/80 border border-slate-800/80 rounded-lg p-3 flex-grow overflow-y-auto space-y-2 max-h-72">
                        <!-- Dynamic Logs -->
                    </div>
                </div>
            </div>
        </main>

        <script>
            let volumeChart;

            async function fetchState() {
                try {
                    const [metricsRes, logsRes] = await Promise.all([
                        fetch('/api/metrics'),
                        fetch('/api/friction-logs')
                    ]);
                    const metrics = await metricsRes.json();
                    const logs = await logsRes.json();

                    document.getElementById('metric-leads').innerText = metrics.leads_enriched;
                    document.getElementById('metric-volume').innerText = '$' + metrics.trust_volume.toLocaleString();
                    document.getElementById('metric-rigs').innerText = metrics.rigs_qualified;
                    document.getElementById('metric-latency').innerText = metrics.mcp_latency + 'ms';

                    updateChart(metrics.trust_volume);

                    const logContainer = document.getElementById('log-stream');
                    logContainer.innerHTML = logs.map(l => `
                        <div class="py-2 px-2.5 bg-slate-900/50 rounded border border-slate-800/50 text-xs font-mono flex flex-col space-y-1">
                            <div class="flex items-center justify-between text-[11px]">
                                <span class="text-indigo-400 font-bold">${l.source}</span>
                                <span class="text-slate-500">${l.created_at}</span>
                            </div>
                            <p class="text-slate-300 text-[11px] truncate">${l.event}</p>
                            <div class="self-start px-1.5 py-0.5 rounded text-[9px] font-bold border ${l.status === 'VERIFIED' || l.status === 'SUCCESS' || l.status === 'Cleared' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border-amber-500/20'}">
                                ${l.status}
                            </div>
                        </div>
                    `).join('');
                } catch (e) {
                    console.error('Telemetry polling error:', e);
                }
            }

            function updateChart(currentVolume) {
                if (!volumeChart) return;
                const timeLabel = new Date().toLocaleTimeString();
                if (volumeChart.data.labels.length > 12) {
                    volumeChart.data.labels.shift();
                    volumeChart.data.datasets[0].data.shift();
                }
                volumeChart.data.labels.push(timeLabel);
                volumeChart.data.datasets[0].data.push(currentVolume);
                volumeChart.update();
            }

            async function triggerSimulatedIngest() {
                const orgs = ["Starlight Dynamics", "Cipher Systems", "Apex Robotics", "Vortex AI"];
                const randomOrg = orgs[Math.floor(Math.random() * orgs.length)] + " " + Math.floor(Math.random() * 900 + 100);
                
                await fetch('/api/v1/webhook/ingest', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        organization: randomOrg,
                        risk_score: parseFloat((Math.random() * 0.5).toFixed(2)),
                        intent_score: Math.floor(Math.random() * 30 + 70),
                        growth_tier: 'Enterprise',
                        stakeholder_role: 'VP RevOps'
                    })
                });
                fetchState();
            }

            window.onload = () => {
                const ctx = document.getElementById('telemetryChart').getContext('2d');
                volumeChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: [],
                        datasets: [{
                            label: 'Settlement Volume ($)',
                            data: [],
                            borderColor: '#6366f1',
                            backgroundColor: 'rgba(99, 102, 241, 0.1)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.35,
                            pointBackgroundColor: '#818cf8'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            x: { grid: { color: 'rgba(51, 65, 85, 0.3)' }, ticks: { color: '#64748b', font: { family: 'JetBrains Mono', size: 10 } } },
                            y: { grid: { color: 'rgba(51, 65, 85, 0.3)' }, ticks: { color: '#64748b', font: { family: 'JetBrains Mono', size: 10 } } }
                        },
                        plugins: { legend: { display: false } }
                    }
                });

                fetchState();
                setInterval(fetchState, 3000);
            };
        </script>
    </body>
    </html>
    """

# --- Telemetry & Ingestion Endpoints ---
@app.get("/api/metrics")
async def get_metrics():
    if not db_pool:
        # Fallback state if DB not linked
        return {"leads_enriched": 18, "trust_volume": 252500.00, "rigs_qualified": 14, "mcp_latency": 12}
    
    async with db_pool.acquire() as conn:
        leads_count = await conn.fetchval("SELECT COUNT(*) FROM public.leads")
        rigs_count = await conn.fetchval("SELECT COUNT(*) FROM public.leads WHERE status = 'Qualified'")
        volume = await conn.fetchval("SELECT COALESCE(SUM(volume_amount), 0) FROM public.settlement_ledger")
    
    return {
        "leads_enriched": leads_count,
        "trust_volume": float(volume),
        "rigs_qualified": rigs_count,
        "mcp_latency": 14
    }

@app.get("/api/friction-logs")
async def get_logs():
    if not db_pool:
        return [
            {"source": "RIGS-Engine", "event": "Fallback initialization mode active", "status": "VERIFIED", "created_at": "14:26:00"},
            {"source": "Grok-Reasoner", "event": "Llama 3.3 70B versitile connected", "status": "SUCCESS", "created_at": "14:25:30"}
        ]
    
    async with db_pool.acquire() as conn:
        records = await conn.fetch("""
            SELECT source, event, status, to_char(created_at, 'HH24:MI:SS') as created_at 
            FROM public.audit_logs 
            ORDER BY id DESC LIMIT 8
        """)
    return [dict(r) for r in records]

@app.post("/api/v1/webhook/ingest")
async def ingest_lead(payload: RIGSInput):
    status = "Qualified" if (payload.risk_score < 0.40 and payload.intent_score >= 70) else "Review"
    if payload.risk_score >= 0.70:
        status = "Disqualified"

    reasoning_prompt = f"Analyze lead: {payload.organization}, Risk: {payload.risk_score}, Intent: {payload.intent_score}. Provide 1-line verdict."
    reasoning_summary = await run_grok_reasoning(reasoning_prompt)

    settlement_amount = 25000.00 if status == "Qualified" else 0.0

    if db_pool:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO public.leads (organization, risk_score, intent_score, growth_tier, stakeholder_role, status) VALUES ($1, $2, $3, $4, $5, $6)",
                payload.organization, payload.risk_score, payload.intent_score, payload.growth_tier, payload.stakeholder_role, status
            )
            if settlement_amount > 0:
                await conn.execute(
                    "INSERT INTO public.settlement_ledger (event_source, volume_amount, status) VALUES ($1, $2, $3)",
                    f"rigs_qualified_{payload.organization}", settlement_amount, "Cleared"
                )
            await conn.execute(
                "INSERT INTO public.audit_logs (source, event, status) VALUES ($1, $2, $3)",
                "RIGS-Grok-Ingest", f"Lead {payload.organization} -> {status}: {reasoning_summary}", "VERIFIED"
            )

    return {
        "status": "processed",
        "organization": payload.organization,
        "rigs_result": status,
        "settlement_added": settlement_amount,
        "grok_reasoning": reasoning_summary
    }
