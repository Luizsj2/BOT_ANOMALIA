FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Só o código. A credencial do Google entra como secret no compose, nunca na imagem.
COPY ["BOT POWER/bot_anomalias.py", "BOT POWER/agendador.py", "./"]

CMD ["python", "agendador.py"]
