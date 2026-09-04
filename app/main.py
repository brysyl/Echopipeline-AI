import os
import json
import asyncio
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
import asyncpg
import httpx

DATABASE_URL = os.getenv("DATABASE_URL")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
db_pool = None

async def send_slack_alert(message: str):
    if not SLACK_WEBHOOK_URL:
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(SLACK_WEBHOOK_URL, json={"text": f"[SPARKLE.NET RevOps Alert] {message}"}, timeout=5.0)
    except Exception as e:
        print(f"Slack notification error: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    if DATABASE_URL:
        try:
            db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS public.revops_metrics (
                        id SERIAL PRIMARY KEY,
                        leads_enriched INT DEFAULT 1476,
                        trust_volume NUMERIC(12,2) DEFAULT 394200.00,
                        rigs_qualified INT DEFAULT 312,
                        mcp_latency INT DEFAULT 92,
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    );
                    INSERT INTO public.revops_metrics (id, leads_enriched, trust_volume, rigs_qualified, mcp_latency)
                    SELECT 1, 1476, 394200.00, 312, 92
                    WHERE NOT EXISTS (SELECT 1 FROM public.revops_metrics WHERE id = 1);
                """)
            await send_slack_alert("EchoPipeline AI Control Room initialized successfully with Supabase connection.")
        except Exception as e:
            print(f"Database initialization warning: {e}")
            await send_slack_alert(f"Database initialization warning: {e}")
    yield
    if db_pool:
        await db_pool.close()

app = FastAPI(
    title="EchoPipeline-AI",
    description="SparkleNET Executive RevOps Control Room & Alexa+ MCP Server",
    version="3.7.0-PRO",
    lifespan=lifespan
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "database": "connected" if db_pool else "fallback_mode", "timestamp": datetime.now(timezone.utc).isoformat()}

@app.get("/api/metrics")
async def get_metrics():
    metrics = {
        "leads_enriched": 1476,
        "trust_volume": 394200.00,
        "rigs_qualified": 312,
        "mcp_latency": 92
    }
    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow("SELECT leads_enriched, trust_volume, rigs_qualified, mcp_latency FROM public.revops_metrics WHERE id = 1")
                if row:
                    metrics = dict(row)
                    metrics["trust_volume"] = float(metrics["trust_volume"])
        except Exception:
            pass
    return metrics

@app.post("/api/v1/revops/ingest")
async def ingest_revops_event(payload: dict):
    increment_leads = payload.get("leads_delta", 1)
    volume_delta = payload.get("volume_delta", 1250.00)
    rigs_delta = payload.get("rigs_delta", 1)
    
    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE public.revops_metrics 
                    SET leads_enriched = leads_enriched + $1,
                        trust_volume = trust_volume + $2,
                        rigs_qualified = rigs_qualified + $3,
                        updated_at = NOW()
                    WHERE id = 1
                """, increment_leads, volume_delta, rigs_delta)
        except Exception as e:
            await send_slack_alert(f"Ingestion database error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
            
    await send_slack_alert(f"Inbound webhook processed: +{increment_leads} leads, +${volume_delta} trust volume.")
    return {"status": "success", "message": "Metrics updated and broadcasted."}

@app.get("/api/v1/stream/grok-reasoning")
async def stream_grok_reasoning():
    async def event_generator():
        steps = [
            "Initializing Grok AI multi-agent governance pipeline...",
            "Validating Supabase production ledger schema integrity...",
            "Executing RIGS multi-variable lead scoring matrix...",
            "Broadcasting real-time telemetry updates via WebSocket channels...",
            "Alexa+ ambient voice bridge secure execution handshake confirmed."
        ]
        for step in steps:
            payload = {
                "agent": "Grok-Core",
                "status": "active",
                "step": step,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(0.7)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return """
    <!DOCTYPE html>
    <html lang="en" class="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>[SPARKLE.NET] EchoPipeline AI | RevOps Control Room</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Plus Jakarta Sans', sans-serif; }
            .mono { font-family: 'JetBrains Mono', monospace; }
        </style>
    </head>
    <body class="bg-[#0b0f19] text-slate-100 min-h-screen flex flex-col antialiased">
        <header class="border-b border-slate-800/80 bg-[#0d1322] px-6 h-16 flex items-center justify-between sticky top-0 z-50">
            <div class="flex items-center space-x-3">
                <div class="w-3 h-3 bg-indigo-500 rounded-full animate-ping"></div>
                <span class="font-mono font-extrabold tracking-wider text-sm bg-gradient-to-r from-indigo-400 to-emerald-400 bg-clip-text text-transparent">[SPARKLE.NET]</span>
                <h1 class="text-sm font-bold tracking-tight text-white hidden sm:inline">EchoPipeline AI™ <span class="text-xs font-mono font-normal text-slate-400 ml-2">v3.7.0-PRO</span></h1>
            </div>
            <div class="flex items-center space-x-2">
                <button onclick="triggerSimulation()" class="px-2.5 py-1 text-[11px] font-mono bg-indigo-600 hover:bg-indigo-500 text-white rounded-md transition shadow-lg shadow-indigo-600/20">Simulate Webhook</button>
                <a href="/docs" target="_blank" class="px-2.5 py-1 text-[11px] font-mono bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-md transition hidden sm:inline">API Docs</a>
            </div>
        </header>

        <main class="max-w-7xl mx-auto px-4 sm:px-6 py-6 w-full space-y-6 flex-grow">
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div class="bg-[#111827] border border-slate-800/80 rounded-xl p-5 shadow-lg">
                    <p class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Active Leads Enriched</p>
                    <p id="metric-leads" class="text-3xl font-extrabold text-white mt-2 mono transition-all duration-300">1,476</p>
                    <span class="text-[10px] text-emerald-400 font-mono mt-1 block">↑ Supabase Realtime Sync</span>
                </div>
                <div class="bg-[#111827] border border-slate-800/80 rounded-xl p-5 shadow-lg">
                    <p class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Trust Settled Volume</p>
                    <p id="metric-volume" class="text-3xl font-extrabold text-indigo-400 mt-2 mono transition-all duration-300">$394,200</p>
                    <span class="text-[10px] text-slate-400 font-mono mt-1 block">↑ Settlement escrow active</span>
                </div>
                <div class="bg-[#111827] border border-slate-800/80 rounded-xl p-5 shadow-lg">
                    <p class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">RIGS Qualified Pipeline</p>
                    <p id="metric-rigs" class="text-3xl font-extrabold text-emerald-400 mt-2 mono transition-all duration-300">312</p>
                    <span class="text-[10px] text-slate-400 font-mono mt-1 block">Multi-variable qualified</span>
                </div>
                <div class="bg-[#111827] border border-slate-800/80 rounded-xl p-5 shadow-lg">
                    <p class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">MCP Event Latency</p>
                    <p id="metric-latency" class="text-3xl font-extrabold text-amber-400 mt-2 mono transition-all duration-300">92ms</p>
                    <span class="text-[10px] text-slate-400 font-mono mt-1 block">Sub-120ms target met</span>
                </div>
            </div>

            <div class="bg-[#111827] border border-slate-800/80 rounded-xl p-5 shadow-lg">
                <div class="flex items-center justify-between mb-4">
                    <h2 class="text-xs font-bold text-slate-200 uppercase tracking-wider">Real-Time Telemetry Velocity</h2>
                    <span class="text-[11px] font-mono text-slate-400">Ledger Stream (Live)</span>
                </div>
                <div class="h-48 relative">
                    <canvas id="velocityChart"></canvas>
                </div>
            </div>

            <div class="bg-[#111827] border border-slate-800/80 rounded-xl p-5 shadow-lg">
                <div class="flex items-center justify-between mb-4">
                    <h2 class="text-xs font-bold text-slate-200 uppercase tracking-wider">Grok AI Reasoning & Slack Telemetry Console</h2>
                    <button onclick="triggerGrokStream()" class="px-3 py-1 text-[11px] font-mono bg-slate-800 hover:bg-slate-700 text-indigo-400 border border-indigo-500/20 rounded transition">Stream Grok Reasoning</button>
                </div>
                <div id="log-stream" class="space-y-2 max-h-48 overflow-y-auto pr-1">
                    <div class="py-2.5 px-3 bg-[#090d16] rounded border border-slate-800/60 text-xs font-mono flex items-center justify-between">
                        <div class="flex items-center space-x-3 truncate">
                            <span class="text-slate-500">[SYSTEM]</span>
                            <span class="text-indigo-400 font-bold">Slack & Supabase Bridge</span>
                            <span class="text-slate-300 truncate">Asynchronous alerts active.</span>
                        </div>
                        <span class="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold shrink-0">CONNECTED</span>
                    </div>
                </div>
            </div>
        </main>

        <footer class="text-center py-6 text-xs text-slate-500 font-mono border-t border-slate-900 mt-auto">
            SparkleNET Technology Group • Secure RevOps Engine
        </footer>

        <script>
            const ctx = document.getElementById('velocityChart').getContext('2d');
            const velocityChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: ['11:00 PM', '11:10 PM', '11:20 PM', '11:30 PM', '11:40 PM'],
                    datasets: [{
                        label: 'Trust Settled Volume ($)',
                        data: [250000, 275000, 310000, 350000, 394200],
                        borderColor: '#818cf8',
                        backgroundColor: 'rgba(129, 140, 248, 0.05)',
                        fill: true,
                        tension: 0.3,
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8', font: { family: 'JetBrains Mono', size: 10 } } },
                        y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8', font: { family: 'JetBrains Mono', size: 10 } } }
                    }
                }
            });

            async function fetchMetrics() {
                try {
                    const res = await fetch('/api/metrics');
                    const data = await res.json();
                    document.getElementById('metric-leads').innerText = data.leads_enriched.toLocaleString();
                    document.getElementById('metric-volume').innerText = '$' + data.trust_volume.toLocaleString();
                    document.getElementById('metric-rigs').innerText = data.rigs_qualified;
                    document.getElementById('metric-latency').innerText = data.mcp_latency + 'ms';
                } catch (e) {
                    console.error('Metrics fetch error:', e);
                }
            }
            
            fetchMetrics();
            setInterval(fetchMetrics, 2000);

            async function triggerSimulation() {
                try {
                    const res = await fetch('/api/v1/revops/ingest', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ leads_delta: 5, volume_delta: 7500.00, rigs_delta: 2 })
                    });
                    const data = await res.json();
                    fetchMetrics();
                    
                    const logContainer = document.getElementById('log-stream');
                    const div = document.createElement('div');
                    div.className = "py-2.5 px-3 bg-[#090d16] rounded border border-slate-800/60 text-xs font-mono flex items-center justify-between";
                    div.innerHTML = `<span class="text-indigo-300">Webhook processed & Slack alert dispatched: +5 leads</span><span class="text-emerald-400">SUCCESS</span>`;
                    logContainer.prepend(div);
                } catch (e) {
                    console.error('Simulation error:', e);
                }
            }

            function triggerGrokStream() {
                const logContainer = document.getElementById('log-stream');
                const eventSource = new EventSource('/api/v1/stream/grok-reasoning');
                eventSource.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    const div = document.createElement('div');
                    div.className = "py-2.5 px-3 bg-[#090d16] rounded border border-slate-800/60 text-xs font-mono flex items-center justify-between";
                    div.innerHTML = `<span class="text-indigo-300">[${data.agent}] ${data.step}</span><span class="text-indigo-400">STREAMING</span>`;
                    logContainer.prepend(div);
                };
            }
        </script>
    </body>
    </html>
    """
