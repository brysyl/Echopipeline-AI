FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONPATH=.
EXPOSE 8000
RUN touch app/__init__.py 2>/dev/null || true
CMD python3 -c "import uvicorn, os; uvicorn.run('app.main:app', host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))"
