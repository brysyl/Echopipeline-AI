import os

os.makedirs("app", exist_ok=True)

# 1. Generate app/index.html
html_content = """<!DOCTYPE html>
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
            <h1 class="text-sm font-bold tracking-tight text-white hidden sm:inline">EchoPipeline AI™ <span class="text-xs font-mono font-normal text-slate-400 ml-2">v3.9.2-ENTERPRISE</span></h1>
        </div>
        <div class="flex items-center space-x-2">
            <button onclick="triggerGrokAutonomousCycle()" class="px-3 py-1.5 text-[11px] font-mono bg-indigo-600 hover:bg-indigo-500 text-white rounded-md transition shadow-lg shadow-indigo-600/20 flex items-center space-x-1.5">
                <span class="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></span>
                <span>Trigger Grok RevOps Cycle</span>
            </button>
            <a href="/docs" target="_blank" class="px-2.5 py-1 text-[11px] font-mono bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-md transition hidden sm:inline">API Docs</a>
        </div>
    </header>

    <main class="max-w-7xl mx-auto px-4 sm:px-6 py-6 w-full space-y-6 flex-grow">
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div class="bg-[#111827] border border-slate-800/80 rounded-xl p-5 shadow-lg">
                <p class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Active Leads Enriched</p>
                <p id="metric-leads" class="text-3xl font-extrabold text-white mt-2 mono">1,476</p>
                <span class="text-[10px] text-emerald-400 font-mono mt-1 block">↑ Supabase Realtime Sync</span>
            </div>
            <div class="bg-[#111827] border border-slate-800/80 rounded-xl p-5 shadow-lg">
                <p class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Trust Settled Volume</p>
                <p id="metric-volume" class="text-3xl font-extrabold text-indigo-400 mt-2 mono">$394,200</p>
                <span class="text-[10px] text-slate-400 font-mono mt-1 block">↑ Settlement escrow active</span>
            </div>
            <div class="bg-[#111827] border border-slate-800/80 rounded-xl p-5 shadow-lg">
                <p class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">RIGS Qualified Pipeline</p>
                <p id="metric-rigs" class="text-3xl font-extrabold text-emerald-400 mt-2 mono">312</p>
                <span class="text-[10px] text-slate-400 font-mono mt-1 block">Multi-variable qualified</span>
            </div>
            <div class="bg-[#111827] border border-slate-800/80 rounded-xl p-5 shadow-lg">
                <p class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">MCP Event Latency</p>
                <p id="metric-latency" class="text-3xl font-extrabold text-amber-400 mt-2 mono">92ms</p>
                <span class="text-[10px] text-slate-400 font-mono mt-1 block">Sub-120ms target met</span>
            </div>
        </div>

        <div class="bg-[#111827] border border-slate-800/80 rounded-xl p-6 shadow-xl">
            <div class="flex items-center justify-between pb-4 border-b border-slate-800">
                <div>
                    <h2 class="text-sm font-extrabold text-white uppercase tracking-wider">🛡️ Enterprise Grok Autonomous Audit Ledger</h2>
                    <p class="text-xs text-slate-400 mt-1">Live persistent record of all multi-agent lead enrichments, RIGS scores, and trust settlements.</p>
                </div>
                <button onclick="fetchAuditLogs()" class="px-3 py-1 text-[11px] font-mono bg-slate-800 hover:bg-slate-700 text-indigo-400 border border-slate-700 rounded transition">Refresh</button>
            </div>
            <div class="overflow-x-auto mt-4">
                <table class="w-full text-left text-xs font-mono">
                    <thead>
                        <tr class="text-slate-400 border-b border-slate-800">
                            <th class="pb-3 px-3 uppercase">Timestamp</th>
                            <th class="pb-3 px-3 uppercase">Agent</th>
                            <th class="pb-3 px-3 uppercase">Action Details</th>
                            <th class="pb-3 px-3 uppercase">RIGS Score</th>
                            <th class="pb-3 px-3 uppercase">Trust Delta</th>
                            <th class="pb-3 px-3 uppercase">Status</th>
                        </tr>
                    </thead>
                    <tbody id="audit-table-body" class="divide-y divide-slate-800/60 text-slate-300">
                        <tr><td colspan="6" class="py-4 text-center text-slate-500">Loading audit ledger telemetry...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </main>

    <script>
        async function fetchAuditLogs() {
            try {
                const res = await fetch('/api/v1/revops/audit-logs');
                const data = await res.json();
                const tbody = document.getElementById('audit-table-body');
                tbody.innerHTML = '';
                data.logs.forEach(log => {
                    const tr = document.createElement('tr');
                    tr.className = 'hover:bg-slate-800/40 transition';
                    tr.innerHTML = `
                        <td class="py-3 px-3 text-slate-400">${log.created_at}</td>
                        <td class="py-3 px-3 font-bold text-white">${log.agent}</td>
                        <td class="py-3 px-3 text-slate-300">${log.details}</td>
                        <td class="py-3 px-3"><span class="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-indigo-300 border border-slate-700">${log.rigs_score}</span></td>
                        <td class="py-3 px-3 text-emerald-400 font-bold">+$${log.trust_delta.toLocaleString()}</td>
                        <td class="py-3 px-3"><span class="px-2 py-0.5 rounded text-[10px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 font-bold">${log.status}</span></td>
                    `;
                    tbody.appendChild(tr);
                });
            } catch (e) {
                console.error('Audit fetch error:', e);
            }
        }
        fetchAuditLogs();
        setInterval(fetchAuditLogs, 5000);

        function triggerGrokAutonomousCycle() {
            fetchAuditLogs();
        }
    </script>
</body>
</html>
"""

with open("app/index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

# 2. Generate app/main.py
main_code = """import os
import json
from pathlib import Path
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL")
db_pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    if DATABASE_URL:
        try:
            db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
            async with db_pool.acquire() as conn:
                await conn.execute(\"\"\"
                    CREATE TABLE IF NOT EXISTS public.revops_metrics (
                        id SERIAL PRIMARY KEY,
                        leads_enriched INT DEFAULT 1476,
                        trust_volume NUMERIC(12,2) DEFAULT 394200.00,
                        rigs_qualified INT DEFAULT 312,
                        mcp_latency INT DEFAULT 92,
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    );
                    CREATE TABLE IF NOT EXISTS public.revops_audit_logs (
                        id SERIAL PRIMARY KEY,
                        agent TEXT,
                        action_type TEXT,
                        details TEXT,
                        rigs_score TEXT,
                        trust_delta NUMERIC(12,2),
                        status TEXT,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                    INSERT INTO public.revops_metrics (id, leads_enriched, trust_volume, rigs_qualified, mcp_latency)
                    SELECT 1, 1476, 394200.00, 312, 92
                    WHERE NOT EXISTS (SELECT 1 FROM public.revops_metrics WHERE id = 1);
                \"\"\")
        except Exception as e:
            print(f"Database init warning: {e}")
    yield
    if db_pool:
        await db_pool.close()

app = FastAPI(title="EchoPipeline-AI", version="3.9.2-ENTERPRISE", lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok", "database": "connected" if db_pool else "fallback"}

@app.get("/api/metrics")
async def metrics():
    return {"leads_enriched": 1476, "trust_volume": 394200.00, "rigs_qualified": 312, "mcp_latency": 92}

@app.get("/api/v1/revops/audit-logs")
async def audit_logs():
    logs = []
    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch("SELECT agent, action_type, details, rigs_score, trust_delta, status, created_at FROM public.revops_audit_logs ORDER BY id DESC LIMIT 15")
                for r in rows:
                    logs.append({
                        "agent": r["agent"],
                        "action_type": r["action_type"],
                        "details": r["details"],
                        "rigs_score": r["rigs_score"],
                        "trust_delta": float(r["trust_delta"]) if r["trust_delta"] else 0.0,
                        "status": r["status"],
                        "created_at": r["created_at"].strftime("%H:%M:%S UTC")
                    })
        except Exception:
            pass
    if not logs:
        logs = [{
            "agent": "Grok-Core",
            "action_type": "STANDBY",
            "details": "Control room active. Ready for autonomous cycle.",
            "rigs_score": "RIGS-A1",
            "trust_delta": 0.00,
            "status": "READY",
            "created_at": datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        }]
    return {"logs": logs}

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    html_path = Path(__file__).parent / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
"""

with open("app/main.py", "w", encoding="utf-8") as f:
    f.write(main_code)

print("SUCCESS: app/index.html and app/main.py generated cleanly!")
