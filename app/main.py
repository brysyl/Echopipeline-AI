from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(
    title="EchoPipeline-AI",
    description="Enterprise-grade ambient RevOps automation bridge for Amazon Alexa+ Track",
    version="1.0.0"
)

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>EchoPipeline-AI Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-950 text-slate-100 font-sans antialiased min-h-screen flex flex-col justify-between">
        <div class="max-w-4xl mx-auto p-6 w-full">
            <header class="flex justify-between items-center border-b border-slate-800 pb-4 mb-8">
                <div>
                    <h1 class="text-2xl font-bold tracking-tight text-white">EchoPipeline-AI</h1>
                    <p class="text-sm text-slate-400">Ambient RevOps Automation Bridge &bull; Amazon Alexa+ Track</p>
                </div>
                <span class="px-3 py-1 text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-full">Operational</span>
            </header>

            <main class="grid gap-6">
                <div class="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
                    <h2 class="text-lg font-semibold text-white mb-2">Quick Navigation</h2>
                    <p class="text-sm text-slate-400 mb-4">Access interactive API documentation, system health probes, and model endpoints.</p>
                    <div class="flex flex-wrap gap-3">
                        <a href="/docs" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors">Swagger Docs</a>
                        <a href="/health" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-lg transition-colors border border-slate-700">Health Check</a>
                    </div>
                </div>

                <div class="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
                    <h2 class="text-lg font-semibold text-white mb-2">System Architecture</h2>
                    <ul class="text-sm text-slate-400 space-y-2">
                        <li>&bull; <strong>Protocol:</strong> Model Context Protocol (MCP) Streamable HTTP</li>
                        <li>&bull; <strong>Runtime:</strong> Python FastAPI on Railway Container</li>
                        <li>&bull; <strong>Target Hackathon:</strong> Amazon Developer (Alexa+ Track)</li>
                    </ul>
                </div>
            </main>
        </div>
        <footer class="border-t border-slate-900 py-4 text-center text-xs text-slate-600">
            EchoPipeline-AI &bull; SparkleNET Technology Group
        </footer>
    </body>
    </html>
    """

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "EchoPipeline-AI"}
