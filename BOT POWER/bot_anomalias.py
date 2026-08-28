import requests
import json
import time
import gspread
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

HOST_IXC = "sistema.powertelecom.net.br"
TOKEN_IXC = "COLOQUE_O_TOKEN_AQUI"
NOME_PLANILHA_ANOMALIAS = "Anomalias Fibra" 
ARQUIVO_CREDENCIAIS = 'loginsoff-53caf8e1c07e.json'


ASSUNTOS_COM_OBSERVACAO = ["67", "118", "119", "18", "101", "127"]

def conectar_planilha():
    try:
        client = gspread.service_account(filename=ARQUIVO_CREDENCIAIS)
        return client.open(NOME_PLANILHA_ANOMALIAS).sheet1
    except Exception as e:
        print(f"❌ Erro Google Sheets: {e}")
        return None

def buscar_sinais_ixc():
    headers = {'ixcsoft': 'listar', 'Content-Type': 'application/json'}
    usuario, senha = TOKEN_IXC.split(':')
    url = f"https://{HOST_IXC}/webservice/v1/radpop_radio_cliente_fibra"
    
    anomalias_brutas = {}
    pagina = 1
    print("🔄 [1/4] Varrendo sinais de fibra...")
    
    while True:
        payload = json.dumps({"qtype": "radpop_radio_cliente_fibra.id", "query": "", "oper": "!=", "page": str(pagina), "rp": "1000", "sortname": "radpop_radio_cliente_fibra.id", "sortorder": "desc"})
        try:
            resp = requests.get(url, headers=headers, auth=(usuario, senha), data=payload, timeout=20)
            if resp.status_code != 200: break
            regs = resp.json().get("registros", [])
            if not regs: break
            
            for eq in regs:
                id_pppoe, rx, tx = eq.get("id_login", ""), eq.get("sinal_rx", ""), eq.get("sinal_tx", "")
                if not id_pppoe or not rx or rx in ("0.00", "0", ""): continue
                if not tx or tx in ("0.00", "0", ""): tx = "0"
                    
                try:
                    f_rx, f_tx = float(rx), float(tx)
                    if (f_rx >= -15.0 or f_rx <= -27.0) or (f_tx < -27.0):
                        anomalias_brutas[str(id_pppoe)] = {"nome": eq.get("nome", "Desconhecido"), "rx": f_rx, "tx": f_tx}
                except: continue
            
            if len(regs) < 1000: break
            pagina += 1
        except: break
    return anomalias_brutas

def obter_id_cliente(id_login, usuario, senha, headers):
    url = f"https://{HOST_IXC}/webservice/v1/radusuarios"
    payload = json.dumps({"qtype": "id", "query": str(id_login), "oper": "=", "page": "1", "rp": "1"})
    try:
        r = requests.get(url, headers=headers, auth=(usuario, senha), data=payload, timeout=10)
        if r.status_code == 200 and r.json().get("registros"):
            return str(id_login), str(r.json()["registros"][0].get("id_cliente", ""))
    except: pass
    return str(id_login), ""

def checar_os_e_endereco(id_cliente, usuario, senha, headers):
    url_os = f"https://{HOST_IXC}/webservice/v1/su_oss_chamado"
    payload_os = json.dumps({"qtype": "id_cliente", "query": str(id_cliente), "oper": "=", "page": "1", "rp": "50"})
    observacao, ignorar = "", False
    
    try:
        r_os = requests.get(url_os, headers=headers, auth=(usuario, senha), data=payload_os, timeout=10)
        if r_os.status_code == 200:
            for os in r_os.json().get("registros", []):
                if os.get("status", "") not in ("F", "C"):
                    id_ass = str(os.get("id_assunto", ""))
                    if id_ass in ASSUNTOS_COM_OBSERVACAO:
                        observacao = f"O.S Aberta (Assunto {id_ass})"
                    else:
                        ignorar = True
                        break
    except: pass

    if ignorar: return id_cliente, "IGNORAR", "", "", ""

    url_cli = f"https://{HOST_IXC}/webservice/v1/cliente"
    payload_cli = json.dumps({"qtype": "id", "query": str(id_cliente), "oper": "=", "page": "1", "rp": "1"})
    bairro, id_cidade = "Desconhecido", ""
    try:
        r_cli = requests.get(url_cli, headers=headers, auth=(usuario, senha), data=payload_cli, timeout=10)
        if r_cli.status_code == 200 and r_cli.json().get("registros"):
            bairro = r_cli.json()["registros"][0].get("bairro", "Desconhecido")
            id_cidade = str(r_cli.json()["registros"][0].get("cidade", ""))
            if not bairro.strip(): bairro = "Não preenchido"
    except: pass
    return id_cliente, "OK", bairro, id_cidade, observacao

def executar_sincronizacao():
    t_inicio = time.time()
    
    anomalias_brutas = buscar_sinais_ixc()
    if not anomalias_brutas: return
    
    print(f"⚡ {len(anomalias_brutas)} anomalias detectadas. Convertendo Logins para ID Cliente...")
    usr, snh = TOKEN_IXC.split(':')
    hdrs = {'ixcsoft': 'listar', 'Content-Type': 'application/json'}
    anomalias_por_cliente = {}
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        futs = {executor.submit(obter_id_cliente, pppoe, usr, snh, hdrs): pppoe for pppoe in anomalias_brutas.keys()}
        for f in as_completed(futs):
            pppoe, id_cli = f.result()
            if id_cli: anomalias_por_cliente[id_cli] = {"pppoe": pppoe, **anomalias_brutas[pppoe]}

    print("📊 [2/4] Cruzando dados com a Planilha...")
    planilha = conectar_planilha()
    if not planilha: return

    regs_planilha = {linha[0]: idx for idx, linha in enumerate(planilha.get_all_values()[1:], start=2) if linha}
    
    cli_remover = [c for c in regs_planilha.keys() if c not in anomalias_por_cliente]
    cli_adicionar = [c for c in anomalias_por_cliente.keys() if c not in regs_planilha]

    if cli_remover:
        print(f"🧹 Removendo {len(cli_remover)} clientes normalizados...")
        reqs = [{"deleteDimension": {"range": {"sheetId": planilha.id, "dimension": "ROWS", "startIndex": r-1, "endIndex": r}}} for r in sorted([regs_planilha[c] for c in cli_remover], reverse=True)]
        if reqs: planilha.spreadsheet.batch_update({"requests": reqs})

    if not cli_adicionar:
        print("✅ Nenhuma anomalia nova. Sincronização concluída!")
        return

    print(f"🚀 [3/4] Checando O.S e Endereço APENAS das {len(cli_adicionar)} novas anomalias...")
    cache_finais, ids_cidades = {}, set()
    with ThreadPoolExecutor(max_workers=20) as executor:
        futs = {executor.submit(checar_os_e_endereco, c, usr, snh, hdrs): c for c in cli_adicionar}
        for f in as_completed(futs):
            id_cli, status, bairro, id_cid, obs = f.result()
            if status != "IGNORAR":
                cache_finais[id_cli] = {"bairro": bairro, "id_cidade": id_cid, "obs": obs}
                if id_cid: ids_cidades.add(id_cid)

    print("🌍 [4/4] Traduzindo Cidades e finalizando...")
    nomes_cidades = {}
    for id_cid in ids_cidades:
        try:
            r_cid = requests.get(f"https://{HOST_IXC}/webservice/v1/cidade", headers=hdrs, auth=(usr, snh), data=json.dumps({"qtype": "id", "query": id_cid, "oper": "=", "page": "1", "rp": "1"}), timeout=10)
            if r_cid.status_code == 200 and r_cid.json().get("registros"):
                nomes_cidades[id_cid] = r_cid.json()["registros"][0].get("nome", "Desconhecida")
        except: pass

    linhas, hr_atual = [], datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    for id_cli, info in cache_finais.items():
        dados = anomalias_por_cliente[id_cli]
        linhas.append([id_cli, dados["nome"], nomes_cidades.get(info["id_cidade"], "Desconhecida"), info["bairro"], str(dados["rx"]), str(dados["tx"]), hr_atual, info["obs"]])
        
    if linhas:
        print(f"📝 Escrevendo {len(linhas)} anomalias na planilha...")
        planilha.append_rows(linhas, value_input_option='USER_ENTERED')

    print(f"\n✅ CONCLUÍDO em {time.time() - t_inicio:.2f}s! Adicionados: {len(linhas)} | Total Ativos: {len(anomalias_por_cliente)}")

if __name__ == "__main__":
    executar_sincronizacao()