"""
api.py — Interface web do sistema de prospecção da Bloco Produções.

Expõe os 6 passos do fluxo via FastAPI + SSE para streaming de logs
em tempo real no navegador.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

app = FastAPI(title="Bloco Produções — Prospecção Outbound")

ARQUIVO_PROSPECTS = Path("dados/prospects.json")
ARQUIVO_AUDITORIA = Path("dados/audit_log.json")
PASTA_APRESENTACOES = Path("apresentacoes")


# ─── Página HTML principal ────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Bloco Produções — Prospecção</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Segoe UI', system-ui, sans-serif;
      background: #0e0e0e;
      color: #e8e8e8;
      min-height: 100vh;
      padding: 32px 24px;
    }
    header {
      max-width: 900px;
      margin: 0 auto 40px;
    }
    header h1 {
      font-size: 1.6rem;
      font-weight: 700;
      letter-spacing: -0.5px;
      color: #fff;
    }
    header p {
      margin-top: 6px;
      font-size: 0.9rem;
      color: #888;
    }
    .grid {
      max-width: 900px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 16px;
    }
    .card {
      background: #1a1a1a;
      border: 1px solid #2a2a2a;
      border-radius: 12px;
      padding: 20px;
      cursor: pointer;
      transition: border-color .2s, background .2s;
    }
    .card:hover { background: #222; border-color: #444; }
    .card.running { border-color: #f0a500; }
    .card.done { border-color: #22c55e; }
    .card.error { border-color: #ef4444; }
    .card-num {
      font-size: 0.7rem;
      color: #555;
      font-weight: 600;
      letter-spacing: 1px;
      text-transform: uppercase;
      margin-bottom: 8px;
    }
    .card-title { font-size: 1rem; font-weight: 600; color: #fff; }
    .card-desc { font-size: 0.8rem; color: #666; margin-top: 4px; }
    .card-status {
      margin-top: 12px;
      font-size: 0.75rem;
      padding: 3px 8px;
      border-radius: 20px;
      display: inline-block;
    }
    .status-idle { background: #1f1f1f; color: #555; }
    .status-running { background: #3a2800; color: #f0a500; }
    .status-done { background: #052e16; color: #22c55e; }
    .status-error { background: #2d0a0a; color: #ef4444; }

    .log-area {
      max-width: 900px;
      margin: 32px auto 0;
      background: #111;
      border: 1px solid #222;
      border-radius: 12px;
      padding: 20px;
    }
    .log-area h2 { font-size: 0.8rem; color: #444; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; }
    #log {
      font-family: 'Courier New', monospace;
      font-size: 0.8rem;
      color: #aaa;
      white-space: pre-wrap;
      max-height: 320px;
      overflow-y: auto;
      line-height: 1.6;
    }
    #log .ok { color: #22c55e; }
    #log .err { color: #ef4444; }
    #log .info { color: #60a5fa; }

    .prospects-area {
      max-width: 900px;
      margin: 24px auto 0;
      background: #111;
      border: 1px solid #222;
      border-radius: 12px;
      padding: 20px;
    }
    .prospects-area h2 { font-size: 0.8rem; color: #444; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 16px; }
    table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
    th { text-align: left; color: #555; font-weight: 600; padding: 6px 10px; border-bottom: 1px solid #222; }
    td { padding: 8px 10px; border-bottom: 1px solid #1a1a1a; vertical-align: middle; }
    tr:hover td { background: #161616; }
    .aprovado-toggle {
      cursor: pointer;
      padding: 3px 10px;
      border-radius: 20px;
      font-size: 0.75rem;
      border: none;
      font-weight: 600;
    }
    .aprovado-true { background: #052e16; color: #22c55e; }
    .aprovado-false { background: #1f1f1f; color: #555; }
    .refresh-btn {
      background: #1a1a1a;
      border: 1px solid #333;
      color: #aaa;
      padding: 6px 14px;
      border-radius: 8px;
      cursor: pointer;
      font-size: 0.8rem;
      margin-left: 12px;
    }
    .refresh-btn:hover { background: #222; }
  </style>
</head>
<body>
  <header>
    <h1>BLOCO. — Sistema de Prospecção Outbound</h1>
    <p>Execute as etapas em ordem. Marque empresas como aprovadas antes de enviar e-mails.</p>
  </header>

  <div class="grid">
    <div class="card" onclick="rodar(1)" id="card-1">
      <div class="card-num">Etapa 01</div>
      <div class="card-title">Buscar Empresas</div>
      <div class="card-desc">DuckDuckGo + Brasil API (Receita Federal)</div>
      <span class="card-status status-idle" id="status-1">Aguardando</span>
    </div>
    <div class="card" onclick="rodar(2)" id="card-2">
      <div class="card-num">Etapa 02</div>
      <div class="card-title">Crawlear Sites</div>
      <div class="card-desc">Extrai conteúdo de cada empresa encontrada</div>
      <span class="card-status status-idle" id="status-2">Aguardando</span>
    </div>
    <div class="card" onclick="rodar(3)" id="card-3">
      <div class="card-num">Etapa 03</div>
      <div class="card-title">Analisar com IA</div>
      <div class="card-desc">Análise audiovisual via Anthropic API</div>
      <span class="card-status status-idle" id="status-3">Aguardando</span>
    </div>
    <div class="card" onclick="rodar(4)" id="card-4">
      <div class="card-num">Etapa 04</div>
      <div class="card-title">Gerar Apresentações</div>
      <div class="card-desc">Cria .md personalizado por empresa</div>
      <span class="card-status status-idle" id="status-4">Aguardando</span>
    </div>
    <div class="card" onclick="rodar(5)" id="card-5">
      <div class="card-num">Etapa 05</div>
      <div class="card-title">Enviar E-mails</div>
      <div class="card-desc">Somente empresas marcadas como aprovadas</div>
      <span class="card-status status-idle" id="status-5">Aguardando</span>
    </div>
    <div class="card" onclick="rodar(6)" id="card-6">
      <div class="card-num">Etapa 06</div>
      <div class="card-title">Ver Auditoria</div>
      <div class="card-desc">Histórico de análises e envios</div>
      <span class="card-status status-idle" id="status-6">Aguardando</span>
    </div>
  </div>

  <div class="log-area">
    <h2>Log de execução</h2>
    <div id="log">Clique em uma etapa para começar...</div>
  </div>

  <div class="prospects-area">
    <h2>
      Empresas encontradas
      <button class="refresh-btn" onclick="carregarProspects()">↻ Atualizar</button>
    </h2>
    <table>
      <thead>
        <tr>
          <th>Empresa</th>
          <th>Setor</th>
          <th>Município</th>
          <th>E-mail</th>
          <th>Aprovado</th>
        </tr>
      </thead>
      <tbody id="prospects-tbody">
        <tr><td colspan="5" style="color:#444;text-align:center;padding:20px">
          Execute a Etapa 1 para carregar empresas.
        </td></tr>
      </tbody>
    </table>
  </div>

  <script>
    let currentEtapa = null;

    function rodar(etapa) {
      if (currentEtapa) return;
      currentEtapa = etapa;

      const log = document.getElementById('log');
      log.innerHTML = '';

      const card = document.getElementById(`card-${etapa}`);
      const status = document.getElementById(`status-${etapa}`);
      card.classList.add('running');
      status.className = 'card-status status-running';
      status.textContent = 'Executando...';

      const es = new EventSource(`/rodar/${etapa}`);

      es.onmessage = (e) => {
        const linha = document.createElement('div');
        const txt = e.data;
        if (txt.includes('ERRO') || txt.includes('ERROR')) linha.className = 'err';
        else if (txt.includes('OK') || txt.includes('Concluído') || txt.includes('salvo')) linha.className = 'ok';
        else if (txt.startsWith('[Etapa')) linha.className = 'info';
        linha.textContent = txt;
        log.appendChild(linha);
        log.scrollTop = log.scrollHeight;
      };

      es.addEventListener('done', (e) => {
        es.close();
        currentEtapa = null;
        card.classList.remove('running');
        const sucesso = e.data === 'ok';
        card.classList.add(sucesso ? 'done' : 'error');
        status.className = `card-status status-${sucesso ? 'done' : 'error'}`;
        status.textContent = sucesso ? 'Concluído' : 'Erro';
        if (etapa === 1) carregarProspects();
      });

      es.onerror = () => {
        es.close();
        currentEtapa = null;
        card.classList.remove('running');
        card.classList.add('error');
        status.className = 'card-status status-error';
        status.textContent = 'Erro de conexão';
      };
    }

    async function toggleAprovado(nome, valor) {
      await fetch('/prospects/aprovar', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({nome, aprovado: valor})
      });
      carregarProspects();
    }

    async function carregarProspects() {
      const resp = await fetch('/prospects');
      if (!resp.ok) return;
      const lista = await resp.json();
      const tbody = document.getElementById('prospects-tbody');
      if (!lista.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="color:#444;text-align:center;padding:20px">Nenhuma empresa encontrada ainda.</td></tr>';
        return;
      }
      tbody.innerHTML = lista.map(e => `
        <tr>
          <td><strong>${e.nome}</strong><br><span style="color:#555;font-size:.75rem">${e.site || ''}</span></td>
          <td>${e.setor || ''}</td>
          <td>${e.municipio || ''}</td>
          <td>${e.email || '—'}</td>
          <td>
            <button
              class="aprovado-toggle aprovado-${e.aprovado}"
              onclick="toggleAprovado(${JSON.stringify(e.nome)}, ${!e.aprovado})"
            >${e.aprovado ? '✓ Aprovado' : 'Aprovar'}</button>
          </td>
        </tr>
      `).join('');
    }

    carregarProspects();
  </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML


# ─── SSE — execução das etapas com streaming de log ──────────────────────────

def capturar_saida(etapa_num: int):
    """Executa a etapa em thread separada e captura stdout linha a linha."""
    import io
    import threading

    fila: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def _rodar():
        import importlib
        modulo_map = {
            1: "etapas._01_busca",
            2: "etapas._02_crawler",
            3: "etapas._03_analise",
            4: "etapas._04_apresentacao",
            5: "etapas._05_email",
            6: "etapas._06_auditoria",
        }
        nome_modulo = modulo_map[etapa_num]

        # Redireciona stdout para capturar prints
        buffer = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buffer

        resultado = "ok"
        try:
            mod = importlib.import_module(nome_modulo)
            importlib.reload(mod)
            mod.executar()
        except Exception as e:
            resultado = f"erro: {e}"
        finally:
            sys.stdout = old_stdout

        # Envia todas as linhas capturadas
        for linha in buffer.getvalue().splitlines():
            asyncio.run_coroutine_threadsafe(fila.put(("msg", linha)), loop)

        asyncio.run_coroutine_threadsafe(fila.put(("done", resultado)), loop)

    threading.Thread(target=_rodar, daemon=True).start()
    return fila


@app.get("/rodar/{etapa}")
async def rodar_etapa(etapa: int):
    if etapa not in range(1, 7):
        return JSONResponse({"erro": "etapa inválida"}, status_code=400)

    fila = capturar_saida(etapa)

    async def gerador():
        while True:
            tipo, dado = await fila.get()
            if tipo == "msg":
                yield f"data: {dado}\n\n"
            else:
                status = "ok" if dado == "ok" else "erro"
                yield f"event: done\ndata: {status}\n\n"
                break

    return StreamingResponse(gerador(), media_type="text/event-stream")


# ─── Prospects — leitura e aprovação ─────────────────────────────────────────

@app.get("/prospects")
async def listar_prospects():
    if not ARQUIVO_PROSPECTS.exists():
        return JSONResponse([])
    dados = json.loads(ARQUIVO_PROSPECTS.read_text(encoding="utf-8"))
    return JSONResponse(dados)


@app.post("/prospects/aprovar")
async def aprovar_prospect(request: Request):
    body = await request.json()
    nome = body.get("nome")
    aprovado = body.get("aprovado", False)

    if not ARQUIVO_PROSPECTS.exists():
        return JSONResponse({"erro": "prospects.json não encontrado"}, status_code=404)

    dados = json.loads(ARQUIVO_PROSPECTS.read_text(encoding="utf-8"))
    for empresa in dados:
        if empresa["nome"] == nome:
            empresa["aprovado"] = aprovado
            break

    ARQUIVO_PROSPECTS.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return JSONResponse({"ok": True})
