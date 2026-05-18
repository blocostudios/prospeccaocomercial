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
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

app = FastAPI(title="Bloco Produções — Prospecção Outbound")
app.mount("/static", StaticFiles(directory="static"), name="static")

ARQUIVO_PROSPECTS = Path("dados/prospects.json")
ARQUIVO_AUDITORIA = Path("dados/audit_log.json")
PASTA_APRESENTACOES = Path("apresentacoes")


# ─── Página HTML principal ────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>BLOCO. — Prospecção</title>
  <style>
    @font-face {
      font-family: 'PPTelegraf';
      src: url('/static/fonts/PPTelegrafRegular.otf') format('opentype');
      font-weight: 400;
      font-style: normal;
    }
    @font-face {
      font-family: 'PPTelegraf';
      src: url('/static/fonts/PPTelegrafRegularOblique.otf') format('opentype');
      font-weight: 400;
      font-style: oblique;
    }
    @font-face {
      font-family: 'PPTelegraf';
      src: url('/static/fonts/PPTelegrafRegularSlanted.otf') format('opentype');
      font-weight: 400;
      font-style: italic;
    }

    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg: #0a0a0a;
      --surface: #111;
      --surface-2: #161616;
      --border: #1e1e1e;
      --border-hover: #333;
      --text: #e2e2e2;
      --text-muted: #555;
      --text-dim: #333;
      --accent: #c8f135;
      --amber: #f0a500;
      --green: #22c55e;
      --red: #ef4444;
    }

    html { scroll-behavior: smooth; }

    body {
      font-family: 'PPTelegraf', 'Helvetica Neue', sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      padding: 0;
    }

    /* ── TOPBAR ── */
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 20px 40px;
      border-bottom: 1px solid var(--border);
      position: sticky;
      top: 0;
      background: rgba(10,10,10,.92);
      backdrop-filter: blur(12px);
      z-index: 100;
    }
    .logo {
      font-size: 1.1rem;
      letter-spacing: 0.12em;
      color: #fff;
      text-transform: uppercase;
    }
    .logo span { color: var(--accent); }
    .topbar-sub {
      font-size: 0.72rem;
      color: var(--text-muted);
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }

    /* ── LAYOUT ── */
    .page { max-width: 1080px; margin: 0 auto; padding: 48px 40px 80px; }

    .section-label {
      font-size: 0.65rem;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--text-dim);
      margin-bottom: 20px;
    }

    /* ── CARDS ── */
    .grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 1px;
      background: var(--border);
      border: 1px solid var(--border);
      border-radius: 2px;
      overflow: hidden;
      margin-bottom: 1px;
    }

    .card {
      background: var(--surface);
      padding: 28px 24px;
      cursor: pointer;
      transition: background .15s;
      position: relative;
      user-select: none;
    }
    .card:hover { background: var(--surface-2); }
    .card.running { background: #110e00; }
    .card.done { background: #071408; }
    .card.error { background: #120606; }

    .card-num {
      font-size: 0.6rem;
      letter-spacing: 0.2em;
      text-transform: uppercase;
      color: var(--text-dim);
      margin-bottom: 16px;
    }
    .card-title {
      font-size: 1.05rem;
      color: #fff;
      margin-bottom: 6px;
      line-height: 1.2;
    }
    .card-desc {
      font-size: 0.75rem;
      color: var(--text-muted);
      line-height: 1.5;
    }
    .card-status {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      margin-top: 20px;
      font-size: 0.68rem;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }
    .card-status::before {
      content: '';
      display: inline-block;
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: currentColor;
    }
    .status-idle { color: var(--text-dim); }
    .status-running { color: var(--amber); animation: pulse 1.2s infinite; }
    .status-done { color: var(--green); }
    .status-error { color: var(--red); }

    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: .4; }
    }

    /* ── LOG ── */
    .panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 2px;
      margin-top: 24px;
      overflow: hidden;
    }
    .panel-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 14px 20px;
      border-bottom: 1px solid var(--border);
    }
    .panel-header h2 {
      font-size: 0.65rem;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--text-dim);
    }
    #log {
      font-family: 'SF Mono', 'Fira Code', monospace;
      font-size: 0.75rem;
      color: #666;
      white-space: pre-wrap;
      max-height: 260px;
      overflow-y: auto;
      line-height: 1.7;
      padding: 16px 20px;
    }
    #log .ok  { color: var(--green); }
    #log .err { color: var(--red); }
    #log .info { color: var(--accent); }

    /* ── PROSPECTS TABLE ── */
    .panel table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.8rem;
    }
    th {
      text-align: left;
      color: var(--text-dim);
      font-size: 0.62rem;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      padding: 12px 16px;
      border-bottom: 1px solid var(--border);
    }
    td {
      padding: 12px 16px;
      border-bottom: 1px solid var(--border);
      vertical-align: middle;
      color: #aaa;
    }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: var(--surface-2); }
    td strong { color: var(--text); font-weight: 400; }
    td .site-url { color: var(--text-dim); font-size: 0.7rem; }

    .btn-aprovar {
      cursor: pointer;
      padding: 4px 12px;
      border-radius: 2px;
      font-size: 0.68rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      border: 1px solid;
      font-family: 'PPTelegraf', sans-serif;
      transition: all .15s;
    }
    .aprovado-true  { border-color: var(--green); color: var(--green); background: transparent; }
    .aprovado-false { border-color: var(--text-dim); color: var(--text-dim); background: transparent; }
    .aprovado-false:hover { border-color: var(--accent); color: var(--accent); }

    .refresh-btn {
      background: transparent;
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 4px 10px;
      border-radius: 2px;
      cursor: pointer;
      font-size: 0.68rem;
      font-family: 'PPTelegraf', sans-serif;
      letter-spacing: 0.06em;
      transition: border-color .15s;
    }
    .refresh-btn:hover { border-color: var(--border-hover); color: var(--text); }

    .empty-state {
      text-align: center;
      padding: 40px;
      color: var(--text-dim);
      font-size: 0.8rem;
      letter-spacing: 0.06em;
    }

    @media (max-width: 720px) {
      .topbar { padding: 16px 20px; }
      .page { padding: 32px 20px 60px; }
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>

  <div class="topbar">
    <div class="logo">BLOCO<span>.</span></div>
    <div class="topbar-sub">Sistema de Prospecção Outbound</div>
  </div>

  <div class="page">

    <div class="section-label">Fluxo de prospecção</div>

    <div class="grid">
      <div class="card" onclick="rodar(1)" id="card-1">
        <div class="card-num">01</div>
        <div class="card-title">Buscar Empresas</div>
        <div class="card-desc">DuckDuckGo + Brasil API — Receita Federal</div>
        <div class="card-status status-idle" id="status-1">Aguardando</div>
      </div>
      <div class="card" onclick="rodar(2)" id="card-2">
        <div class="card-num">02</div>
        <div class="card-title">Crawlear Sites</div>
        <div class="card-desc">Extrai conteúdo de cada empresa encontrada</div>
        <div class="card-status status-idle" id="status-2">Aguardando</div>
      </div>
      <div class="card" onclick="rodar(3)" id="card-3">
        <div class="card-num">03</div>
        <div class="card-title">Analisar com IA</div>
        <div class="card-desc">Análise audiovisual via Anthropic API</div>
        <div class="card-status status-idle" id="status-3">Aguardando</div>
      </div>
      <div class="card" onclick="rodar(4)" id="card-4">
        <div class="card-num">04</div>
        <div class="card-title">Gerar Apresentações</div>
        <div class="card-desc">Cria documento personalizado por empresa</div>
        <div class="card-status status-idle" id="status-4">Aguardando</div>
      </div>
      <div class="card" onclick="rodar(5)" id="card-5">
        <div class="card-num">05</div>
        <div class="card-title">Enviar E-mails</div>
        <div class="card-desc">Somente empresas marcadas como aprovadas</div>
        <div class="card-status status-idle" id="status-5">Aguardando</div>
      </div>
      <div class="card" onclick="rodar(6)" id="card-6">
        <div class="card-num">06</div>
        <div class="card-title">Auditoria</div>
        <div class="card-desc">Histórico completo de análises e envios</div>
        <div class="card-status status-idle" id="status-6">Aguardando</div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <h2>Log de execução</h2>
      </div>
      <div id="log">Selecione uma etapa para iniciar...</div>
    </div>

    <div class="panel" style="margin-top:24px">
      <div class="panel-header">
        <h2>Empresas encontradas</h2>
        <button class="refresh-btn" onclick="carregarProspects()">↻ Atualizar</button>
      </div>
      <table>
        <thead>
          <tr>
            <th>Empresa</th>
            <th>Setor</th>
            <th>Município</th>
            <th>E-mail</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody id="prospects-tbody">
          <tr><td colspan="5" class="empty-state">Execute a Etapa 01 para carregar empresas.</td></tr>
        </tbody>
      </table>
    </div>

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
      card.classList.remove('done','error');
      card.classList.add('running');
      status.className = 'card-status status-running';
      status.textContent = 'Executando';

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
        const ok = e.data === 'ok';
        card.classList.add(ok ? 'done' : 'error');
        status.className = `card-status status-${ok ? 'done' : 'error'}`;
        status.textContent = ok ? 'Concluído' : 'Erro';
        if (etapa === 1) carregarProspects();
      });

      es.onerror = () => {
        es.close();
        currentEtapa = null;
        card.classList.remove('running');
        card.classList.add('error');
        status.className = 'card-status status-error';
        status.textContent = 'Falha de conexão';
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
        tbody.innerHTML = '<tr><td colspan="5" class="empty-state">Nenhuma empresa encontrada ainda.</td></tr>';
        return;
      }
      tbody.innerHTML = lista.map(e => `
        <tr>
          <td>
            <strong>${e.nome}</strong>
            ${e.site ? `<br><span class="site-url">${e.site}</span>` : ''}
          </td>
          <td>${e.setor || '—'}</td>
          <td>${e.municipio || '—'}</td>
          <td>${e.email || '—'}</td>
          <td>
            <button
              class="btn-aprovar aprovado-${e.aprovado}"
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
