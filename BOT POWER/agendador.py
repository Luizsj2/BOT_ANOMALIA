import os
import time
import traceback
from datetime import datetime

import bot_anomalias as bot

# Configuração vem do ambiente (docker-compose / .env), não do código.
bot.TOKEN_IXC = os.environ.get("TOKEN_IXC", "")
bot.ARQUIVO_CREDENCIAIS = os.environ.get("ARQUIVO_CREDENCIAIS", bot.ARQUIVO_CREDENCIAIS)
bot.NOME_PLANILHA_ANOMALIAS = os.environ.get("NOME_PLANILHA", bot.NOME_PLANILHA_ANOMALIAS)
INTERVALO = int(os.environ.get("INTERVALO_MINUTOS", "30")) * 60

if __name__ == "__main__":
    if ":" not in bot.TOKEN_IXC:
        raise SystemExit("❌ TOKEN_IXC ausente ou fora do formato id:token")
    # Se o arquivo não existe no host, o Docker monta uma pasta vazia no lugar.
    if not os.path.isfile(bot.ARQUIVO_CREDENCIAIS):
        raise SystemExit(f"❌ Credencial do Google não é um arquivo: {bot.ARQUIVO_CREDENCIAIS} (confira ARQUIVO_CREDENCIAIS_LOCAL no .env)")

    # Uma rodada por vez: a próxima só começa depois que a anterior termina.
    while True:
        print(f"⏱️ Rodada iniciada em {datetime.now():%d/%m/%Y %H:%M:%S}")
        try:
            bot.executar_sincronizacao()
        except Exception:
            traceback.print_exc()
        print(f"💤 Próxima rodada em {INTERVALO // 60} min")
        time.sleep(INTERVALO)
