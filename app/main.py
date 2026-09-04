import os
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
                await conn.execute("""
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
                """)
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
