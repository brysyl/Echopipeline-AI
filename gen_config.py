import re

with open('app/main.py', 'r') as f:
    content = f.read()

attrs = sorted(list(set(re.findall(r'settings\.([a-zA-Z0-9_]+)', content))))

lines = ['from pydantic_settings import BaseSettings', '', 'class Settings(BaseSettings):']
for attr in attrs:
    if any(k in attr for k in ['enable_', 'mock_', 'is_', 'fallback', 'only', 'debug']):
        lines.append(f'    {attr}: bool = True')
    elif 'port' in attr:
        lines.append(f'    {attr}: int = 8000')
    else:
        lines.append(f'    {attr}: str = "mock-{attr}"')

lines.extend(['', 'settings = Settings()'])

with open('app/config.py', 'w') as f:
    f.write('\n'.join(lines) + '\n')
print("Fixed config generated.")
