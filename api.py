"""
api.py — Interface web do sistema de prospecção da Bloco Produções.
"""

import asyncio
import csv
import io
import json
import os
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

app = FastAPI(title="Bloco Produções — Prospecção Outbound")
app.mount("/static", StaticFiles(directory="static"), name="static")

ARQUIVO_PROSPECTS = Path("dados/prospects.json")
ARQUIVO_AUDITORIA = Path("dados/audit_log.json")
ARQUIVO_LISTAS    = Path("dados/listas.json")
PASTA_APRESENTACOES = Path("apresentacoes")


# ─── Helpers de persistência ──────────────────────────────────────────────────

def ler_listas() -> list:
    if not ARQUIVO_LISTAS.exists():
        return []
    return json.loads(ARQUIVO_LISTAS.read_text(encoding="utf-8"))


def salvar_listas(listas: list):
    ARQUIVO_LISTAS.parent.mkdir(exist_ok=True)
    ARQUIVO_LISTAS.write_text(json.dumps(listas, ensure_ascii=False, indent=2), encoding="utf-8")


# ─── HTML ─────────────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BLOCO. — Prospecção</title>
<style>
@font-face{font-family:'PP';src:url('/static/fonts/PPTelegrafRegular.otf') format('opentype');font-weight:400;font-style:normal}
@font-face{font-family:'PP';src:url('/static/fonts/PPTelegrafRegularOblique.otf') format('opentype');font-weight:400;font-style:oblique}

*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#090909;--s1:#111;--s2:#161616;--bd:#222;--bd2:#2e2e2e;
  --t1:#eaeaea;--t2:#aaa;--t3:#666;--t4:#3a3a3a;
  --ac:#c8f135;--amber:#f0a500;--green:#4ade80;--red:#f87171;
}
html{scroll-behavior:smooth}
body{font-family:'PP','Helvetica Neue',sans-serif;background:var(--bg);color:var(--t1);font-size:15px;line-height:1.7;min-height:100vh}

/* ── TOPBAR ── */
.topbar{display:flex;align-items:center;justify-content:space-between;padding:18px 40px;border-bottom:1px solid var(--bd);position:sticky;top:0;background:rgba(9,9,9,.93);backdrop-filter:blur(14px);z-index:100}
.topbar img{height:28px;width:auto;display:block}
.topbar-sub{font-size:.72rem;color:var(--t3);letter-spacing:.1em;text-transform:uppercase}

/* ── PAGE ── */
.page{max-width:1100px;margin:0 auto;padding:40px 40px 80px}

/* ── STEP CARDS ── */
.steps{display:grid;grid-template-columns:repeat(6,1fr);gap:1px;background:var(--bd);border:1px solid var(--bd);overflow:hidden;border-radius:2px;margin-bottom:32px}
.step{background:var(--s1);padding:18px 16px;cursor:pointer;transition:background .15s;user-select:none;border-bottom:2px solid transparent}
.step:hover{background:var(--s2)}
.step.active{background:var(--s2);border-bottom-color:var(--ac)}
.step.done{border-bottom-color:var(--green)}
.step.error{border-bottom-color:var(--red)}
.step.running{border-bottom-color:var(--amber)}
.step-num{font-size:.6rem;letter-spacing:.2em;text-transform:uppercase;color:var(--t4);margin-bottom:8px}
.step-title{font-size:.88rem;color:var(--t1);line-height:1.3}
.step-badge{display:inline-flex;align-items:center;gap:5px;margin-top:10px;font-size:.65rem;letter-spacing:.1em;text-transform:uppercase;color:var(--t4)}
.step-badge::before{content:'';width:5px;height:5px;border-radius:50%;background:currentColor;display:inline-block}
.step.active .step-badge{color:var(--ac)}
.step.done .step-badge{color:var(--green)}
.step.error .step-badge{color:var(--red)}
.step.running .step-badge{color:var(--amber);animation:pulse 1.2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}

/* ── PAINEL ── */
.painel{background:var(--s1);border:1px solid var(--bd);border-radius:2px;padding:32px;margin-bottom:24px;display:none}
.painel.visible{display:block}
.painel-title{font-size:1.05rem;color:var(--t1);margin-bottom:6px}
.painel-desc{font-size:.88rem;color:var(--t2);line-height:1.7;margin-bottom:28px;max-width:640px}

/* ── FORM ── */
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}
.form-grid .full{grid-column:1/-1}
.field label{display:block;font-size:.73rem;text-transform:uppercase;letter-spacing:.1em;color:var(--t3);margin-bottom:7px}
.field input,.field select{width:100%;background:#0d0d0d;border:1px solid var(--bd2);border-radius:2px;padding:10px 14px;font-size:.93rem;font-family:'PP',sans-serif;color:var(--t1);outline:none;transition:border-color .15s}
.field input:focus,.field select:focus{border-color:var(--ac)}
.field input::placeholder{color:var(--t4)}
.field select option{background:#111}

/* ── BUTTONS ── */
.btn{display:inline-flex;align-items:center;gap:8px;padding:10px 22px;font-size:.85rem;font-family:'PP',sans-serif;border-radius:2px;cursor:pointer;transition:all .15s;letter-spacing:.04em;border:none}
.btn-primary{background:var(--ac);color:#0a0a0a;font-weight:600}
.btn-primary:hover{background:#d4f545}
.btn-primary:disabled{background:#3a4a1a;color:#556020;cursor:not-allowed}
.btn-ghost{background:transparent;border:1px solid var(--bd2);color:var(--t2)}
.btn-ghost:hover{border-color:var(--t3);color:var(--t1)}
.btn-danger{background:transparent;border:1px solid #3a1515;color:var(--red);font-size:.78rem;padding:6px 12px}
.btn-danger:hover{border-color:var(--red)}
.btn-sm{padding:6px 14px;font-size:.78rem}
.btn-row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}

/* ── RESULTADOS DA BUSCA ── */
#resultados-busca{display:none;margin-top:28px}
.resultados-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:12px}
.resultados-header h3{font-size:.88rem;color:var(--t1)}
.resultados-count{font-size:.78rem;color:var(--t3);margin-left:8px}

.tabela-wrapper{overflow-x:auto;border:1px solid var(--bd);border-radius:2px}
table{width:100%;border-collapse:collapse;font-size:.85rem}
thead th{text-align:left;font-size:.68rem;text-transform:uppercase;letter-spacing:.12em;color:var(--t3);padding:11px 14px;border-bottom:1px solid var(--bd);white-space:nowrap;font-weight:400}
tbody td{padding:11px 14px;border-bottom:1px solid var(--bd);color:var(--t2);vertical-align:middle}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover td{background:var(--s2)}
tbody td strong{color:var(--t1);font-weight:400}
.td-site{font-size:.75rem;color:var(--t4);margin-top:2px}

/* Checkbox customizado */
.cb-wrap{display:flex;align-items:center;justify-content:center}
.cb-wrap input[type=checkbox]{width:16px;height:16px;accent-color:var(--ac);cursor:pointer}

/* Salvar lista */
.salvar-lista{display:none;margin-top:24px;padding-top:24px;border-top:1px solid var(--bd)}
.salvar-lista h3{font-size:.85rem;color:var(--t1);margin-bottom:6px}
.salvar-lista p{font-size:.82rem;color:var(--t3);margin-bottom:16px}
.salvar-row{display:flex;gap:12px;align-items:center}
.salvar-row input{flex:1;background:#0d0d0d;border:1px solid var(--bd2);border-radius:2px;padding:10px 14px;font-size:.9rem;font-family:'PP',sans-serif;color:var(--t1);outline:none}
.salvar-row input:focus{border-color:var(--ac)}

/* ── ETAPA 2 PAINEL ── */
.fonte-opcoes{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--bd);border:1px solid var(--bd);border-radius:2px;margin-bottom:24px}
.fonte-opcao{background:var(--s1);padding:24px;cursor:pointer;transition:background .15s}
.fonte-opcao.selected{background:var(--s2);outline:1px solid var(--ac)}
.fonte-opcao h4{font-size:.85rem;color:var(--t1);margin-bottom:4px}
.fonte-opcao p{font-size:.78rem;color:var(--t3);margin-bottom:16px;line-height:1.6}
.fonte-opcao select,.fonte-opcao input[type=file]{width:100%;background:#0d0d0d;border:1px solid var(--bd2);border-radius:2px;padding:9px 12px;font-size:.85rem;font-family:'PP',sans-serif;color:var(--t1);outline:none}
.fonte-opcao select:focus{border-color:var(--ac)}
.upload-hint{font-size:.72rem;color:var(--t4);margin-top:8px}

/* ── LOG ── */
.log-panel{background:var(--s1);border:1px solid var(--bd);border-radius:2px;margin-bottom:24px}
.log-header{display:flex;align-items:center;justify-content:space-between;padding:14px 20px;border-bottom:1px solid var(--bd);cursor:pointer}
.log-header h2{font-size:.7rem;letter-spacing:.16em;text-transform:uppercase;color:var(--t4)}
.log-toggle{font-size:.72rem;color:var(--t3)}
#log{font-family:'SF Mono','Fira Code','Courier New',monospace;font-size:.78rem;color:var(--t3);white-space:pre-wrap;max-height:240px;overflow-y:auto;line-height:1.75;padding:16px 20px}
#log .ok{color:var(--green)}
#log .err{color:var(--red)}
#log .info{color:var(--ac)}
.log-hidden #log{display:none}

/* ── LISTAS SALVAS ── */
.listas-panel{background:var(--s1);border:1px solid var(--bd);border-radius:2px}
.listas-header{display:flex;align-items:center;justify-content:space-between;padding:14px 20px;border-bottom:1px solid var(--bd)}
.listas-header h2{font-size:.7rem;letter-spacing:.16em;text-transform:uppercase;color:var(--t4)}
.listas-grid{padding:20px;display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
.lista-card{background:var(--s2);border:1px solid var(--bd);border-radius:2px;padding:16px}
.lista-nome{font-size:.9rem;color:var(--t1);margin-bottom:4px}
.lista-meta{font-size:.75rem;color:var(--t3)}
.lista-actions{display:flex;gap:8px;margin-top:12px}
.listas-vazio{padding:32px;text-align:center;font-size:.85rem;color:var(--t4)}

/* ── ETAPAS 3-6 ── */
.etapa-simples{display:flex;flex-direction:column;gap:20px}
.etapa-simples .etapa-info{font-size:.88rem;color:var(--t2);line-height:1.75;max-width:580px}

/* ── DIVISOR ── */
.divisor{display:flex;align-items:center;gap:12px;color:var(--t4);font-size:.78rem;margin:4px 0}
.divisor::before,.divisor::after{content:'';flex:1;height:1px;background:var(--bd)}

@media(max-width:800px){
  .topbar{padding:16px 20px}
  .page{padding:24px 16px 60px}
  .steps{grid-template-columns:repeat(3,1fr)}
  .form-grid{grid-template-columns:1fr}
  .fonte-opcoes{grid-template-columns:1fr}
}
</style>
</head>
<body>

<div class="topbar">
  <img src="/static/logo-light.png" alt="BLOCO.">
  <span class="topbar-sub">Sistema de Prospecção Outbound</span>
</div>

<div class="page">

  <!-- Steps -->
  <div class="steps">
    <div class="step" id="step-1" onclick="abrirStep(1)">
      <div class="step-num">01</div>
      <div class="step-title">Buscar Empresas</div>
      <div class="step-badge" id="badge-1">Aguardando</div>
    </div>
    <div class="step" id="step-2" onclick="abrirStep(2)">
      <div class="step-num">02</div>
      <div class="step-title">Crawlear Sites</div>
      <div class="step-badge" id="badge-2">Aguardando</div>
    </div>
    <div class="step" id="step-3" onclick="abrirStep(3)">
      <div class="step-num">03</div>
      <div class="step-title">Analisar com IA</div>
      <div class="step-badge" id="badge-3">Aguardando</div>
    </div>
    <div class="step" id="step-4" onclick="abrirStep(4)">
      <div class="step-num">04</div>
      <div class="step-title">Apresentações</div>
      <div class="step-badge" id="badge-4">Aguardando</div>
    </div>
    <div class="step" id="step-5" onclick="abrirStep(5)">
      <div class="step-num">05</div>
      <div class="step-title">Enviar E-mails</div>
      <div class="step-badge" id="badge-5">Aguardando</div>
    </div>
    <div class="step" id="step-6" onclick="abrirStep(6)">
      <div class="step-num">06</div>
      <div class="step-title">Auditoria</div>
      <div class="step-badge" id="badge-6">Aguardando</div>
    </div>
  </div>

  <!-- Painel dinâmico -->
  <div class="painel" id="painel"></div>

  <!-- Log -->
  <div class="log-panel" id="log-panel">
    <div class="log-header" onclick="toggleLog()">
      <h2>Log de execução</h2>
      <span class="log-toggle" id="log-toggle">▾ expandir</span>
    </div>
    <div id="log">Selecione uma etapa para começar...</div>
  </div>

  <!-- Listas salvas -->
  <div class="listas-panel">
    <div class="listas-header">
      <h2>Listas salvas</h2>
      <button class="btn btn-ghost btn-sm" onclick="carregarListas()">↻ Atualizar</button>
    </div>
    <div id="listas-grid" class="listas-grid">
      <div class="listas-vazio">Nenhuma lista salva ainda.</div>
    </div>
  </div>

</div><!-- /page -->

<script>
/* ── Estado ── */
let stepAtivo = null;
let buscando = false;
let empresasEncontradas = [];
let selecionadas = new Set();
let logAberto = false;
let listasCache = [];

/* ── Steps ── */
function abrirStep(n) {
  // Toggle: fecha se clicar no mesmo step aberto
  if (stepAtivo === n) {
    stepAtivo = null;
    document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
    document.getElementById('painel').classList.remove('visible');
    return;
  }

  stepAtivo = n;
  document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
  document.getElementById('step-'+n).classList.add('active');

  const painel = document.getElementById('painel');
  painel.classList.add('visible');

  if (n === 1) renderPainel1();
  else if (n === 2) renderPainel2();
  else renderPainelSimples(n);
}

/* ── Painel Etapa 1 ── */
function renderPainel1() {
  document.getElementById('painel').innerHTML = `
    <div class="painel-title">Buscar empresas</div>
    <div class="painel-desc">Preencha os campos abaixo para refinar a busca. Todos os campos são opcionais — quanto mais informação, melhor o resultado.</div>

    <div class="form-grid">
      <div class="field">
        <label>Segmento / Setor</label>
        <input id="f-segmento" type="text" placeholder="Ex: advocacia, clínica médica, agência digital">
      </div>
      <div class="field">
        <label>Cidade / Região</label>
        <input id="f-cidade" type="text" placeholder="Ex: Porto Alegre, Sul do Brasil">
      </div>
      <div class="field">
        <label>Porte da empresa</label>
        <select id="f-porte">
          <option value="">Qualquer porte</option>
          <option>Micro</option>
          <option>Pequeno</option>
          <option>Médio</option>
          <option>Grande</option>
        </select>
      </div>
      <div class="field">
        <label>CNAE</label>
        <input id="f-cnae" type="text" placeholder="Ex: 7311-4 ou publicidade e propaganda">
      </div>
      <div class="field full">
        <label>Palavras-chave adicionais</label>
        <input id="f-keywords" type="text" placeholder="Ex: premium, boutique, especializado em, escritório de...">
      </div>
    </div>

    <div class="btn-row">
      <button class="btn btn-primary" id="btn-buscar" onclick="iniciarBusca()">Iniciar Busca</button>
    </div>

    <div id="resultados-busca">
      <div class="resultados-header" style="margin-top:32px">
        <div>
          <h3 style="display:inline">Resultados</h3>
          <span class="resultados-count" id="count-label">0 empresas encontradas</span>
        </div>
        <div class="btn-row">
          <button class="btn btn-ghost btn-sm" onclick="selecionarTodas()">Selecionar todas</button>
          <button class="btn btn-ghost btn-sm" onclick="deselecionarTodas()">Limpar seleção</button>
        </div>
      </div>
      <div class="tabela-wrapper">
        <table>
          <thead>
            <tr>
              <th style="width:40px"></th>
              <th>Empresa</th>
              <th>Setor</th>
              <th>Município</th>
              <th>E-mail</th>
            </tr>
          </thead>
          <tbody id="tbody-resultados"></tbody>
        </table>
      </div>

      <div class="salvar-lista" id="salvar-lista">
        <h3>Salvar lista de prospecção</h3>
        <p><span id="count-selecionadas">0</span> empresa(s) selecionada(s). Dê um nome para esta lista para usá-la nas próximas etapas.</p>
        <div class="salvar-row">
          <input type="text" id="nome-lista" placeholder="Ex: Clínicas Porto Alegre, Advogados Sul...">
          <button class="btn btn-primary" onclick="salvarLista()">Salvar lista</button>
        </div>
      </div>
    </div>
  `;
}

async function iniciarBusca() {
  if (buscando) return;
  buscando = true;
  empresasEncontradas = [];
  selecionadas.clear();

  const btn = document.getElementById('btn-buscar');
  btn.disabled = true;
  btn.textContent = 'Buscando...';

  document.getElementById('step-1').classList.remove('done','error');
  document.getElementById('step-1').classList.add('running');
  setBadge(1, 'running', 'Buscando');

  document.getElementById('resultados-busca').style.display = 'block';
  document.getElementById('salvar-lista').style.display = 'none';
  document.getElementById('tbody-resultados').innerHTML = '';
  document.getElementById('count-label').textContent = '0 empresas encontradas';
  abrirLog();
  limparLog();

  const params = new URLSearchParams({
    segmento: document.getElementById('f-segmento').value,
    cidade:   document.getElementById('f-cidade').value,
    porte:    document.getElementById('f-porte').value,
    cnae:     document.getElementById('f-cnae').value,
    keywords: document.getElementById('f-keywords').value,
  });

  const es = new EventSource('/buscar/stream?' + params.toString());

  es.onmessage = (e) => {
    const d = JSON.parse(e.data);
    if (d.t === 'log') {
      appendLog(d.m);
    } else if (d.t === 'empresa') {
      adicionarEmpresaResultado(d.e);
    }
  };

  es.addEventListener('done', () => {
    es.close();
    buscando = false;
    btn.disabled = false;
    btn.textContent = 'Buscar novamente';
    document.getElementById('step-1').classList.remove('running');
    document.getElementById('step-1').classList.add('done');
    setBadge(1, 'done', empresasEncontradas.length + ' encontradas');
    if (empresasEncontradas.length > 0) {
      document.getElementById('salvar-lista').style.display = 'block';
      atualizarContSelecionadas();
    }
  });

  es.onerror = () => {
    es.close();
    buscando = false;
    btn.disabled = false;
    btn.textContent = 'Tentar novamente';
    document.getElementById('step-1').classList.remove('running');
    document.getElementById('step-1').classList.add('error');
    setBadge(1, 'error', 'Erro');
  };
}

function adicionarEmpresaResultado(e) {
  const idx = empresasEncontradas.length;
  empresasEncontradas.push(e);
  selecionadas.add(idx); // seleciona por padrão

  const tbody = document.getElementById('tbody-resultados');
  const tr = document.createElement('tr');
  tr.id = 'row-'+idx;
  tr.innerHTML = `
    <td class="cb-wrap"><input type="checkbox" checked onchange="toggleEmpresa(${idx}, this.checked)"></td>
    <td><strong>${esc(e.nome)}</strong>${e.site ? '<div class="td-site">'+esc(e.site)+'</div>' : ''}</td>
    <td>${esc(e.setor||'—')}</td>
    <td>${esc(e.municipio||'—')}</td>
    <td>${esc(e.email||'—')}</td>
  `;
  tbody.appendChild(tr);

  document.getElementById('count-label').textContent = empresasEncontradas.length + ' empresa(s) encontrada(s)';
  atualizarContSelecionadas();
}

function toggleEmpresa(idx, checked) {
  if (checked) selecionadas.add(idx);
  else selecionadas.delete(idx);
  atualizarContSelecionadas();
}

function selecionarTodas() {
  empresasEncontradas.forEach((_, i) => selecionadas.add(i));
  document.querySelectorAll('#tbody-resultados input[type=checkbox]').forEach(cb => cb.checked = true);
  atualizarContSelecionadas();
}

function deselecionarTodas() {
  selecionadas.clear();
  document.querySelectorAll('#tbody-resultados input[type=checkbox]').forEach(cb => cb.checked = false);
  atualizarContSelecionadas();
}

function atualizarContSelecionadas() {
  const el = document.getElementById('count-selecionadas');
  if (el) el.textContent = selecionadas.size;
}

async function salvarLista() {
  const nome = document.getElementById('nome-lista').value.trim();
  if (!nome) { alert('Digite um nome para a lista.'); return; }
  if (selecionadas.size === 0) { alert('Selecione ao menos uma empresa.'); return; }

  const empresas = [...selecionadas].map(i => empresasEncontradas[i]);
  const resp = await fetch('/listas', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({nome, empresas})
  });
  if (resp.ok) {
    alert(`Lista "${nome}" salva com ${empresas.length} empresa(s)!`);
    document.getElementById('nome-lista').value = '';
    carregarListas();
  }
}

/* ── Painel Etapa 2 ── */
function renderPainel2() {
  carregarListas().then(() => {
    const opts = listasCache.map(l =>
      `<option value="${l.id}">${esc(l.nome)} (${l.total} empresas)</option>`
    ).join('');

    document.getElementById('painel').innerHTML = `
      <div class="painel-title">Crawlear sites das empresas</div>
      <div class="painel-desc">Selecione de onde virão as empresas para análise: uma lista salva ou um arquivo de upload.</div>

      <div class="fonte-opcoes">
        <div class="fonte-opcao selected" id="opcao-lista" onclick="selecionarFonte('lista')">
          <h4>Lista salva</h4>
          <p>Use uma lista criada na Etapa 1.</p>
          ${listasCache.length > 0
            ? `<select id="sel-lista">${opts}</select>`
            : `<p style="color:var(--t4);font-size:.8rem">Nenhuma lista salva ainda. Execute a Etapa 1 primeiro.</p>`
          }
        </div>
        <div class="fonte-opcao" id="opcao-upload" onclick="selecionarFonte('upload')">
          <h4>Upload de arquivo</h4>
          <p>Envie um arquivo CSV ou XML com a lista de empresas.</p>
          <input type="file" id="input-upload" accept=".csv,.xml">
          <div class="upload-hint">CSV: colunas nome, site, email, telefone (separador vírgula ou ponto-e-vírgula)<br>XML: tags &lt;empresa&gt; com &lt;nome&gt;, &lt;site&gt;, &lt;email&gt;</div>
        </div>
      </div>

      <div class="btn-row">
        <button class="btn btn-primary" onclick="iniciarEtapa2()">Iniciar Etapa 2</button>
      </div>
    `;
  });
}

let fonteEtapa2 = 'lista';
function selecionarFonte(tipo) {
  fonteEtapa2 = tipo;
  document.getElementById('opcao-lista').classList.toggle('selected', tipo === 'lista');
  document.getElementById('opcao-upload').classList.toggle('selected', tipo === 'upload');
}

async function iniciarEtapa2() {
  if (fonteEtapa2 === 'lista') {
    const sel = document.getElementById('sel-lista');
    if (!sel) { alert('Nenhuma lista disponível.'); return; }
    const listaId = sel.value;
    const resp = await fetch('/etapa2/preparar', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({lista_id: listaId})
    });
    if (!resp.ok) { alert('Erro ao preparar lista.'); return; }
  } else {
    const file = document.getElementById('input-upload').files[0];
    if (!file) { alert('Selecione um arquivo.'); return; }
    const form = new FormData();
    form.append('file', file);
    const resp = await fetch('/etapa2/upload', {method:'POST', body:form});
    if (!resp.ok) { alert('Erro ao processar arquivo.'); return; }
  }
  rodarEtapa(2);
}

/* ── Painel Steps 3-6 ── */
const ETAPAS_INFO = {
  3: {titulo:'Analisar com IA', desc:'Para cada empresa com conteúdo capturado, a API da Anthropic gera uma análise de oportunidades audiovisuais personalizada. Salvo em dados/analyses.json.'},
  4: {titulo:'Gerar apresentações', desc:'Cria um documento .md personalizado por empresa com análise, bio da Bloco Produções e plano de ação sugerido. Salvo em /apresentacoes/.'},
  5: {titulo:'Enviar e-mails', desc:'Envia e-mails apenas para empresas marcadas como aprovadas em prospects.json. Usa Gmail OAuth2. Registra envios no audit_log.json.'},
  6: {titulo:'Auditoria', desc:'Exibe o histórico completo de análises geradas e e-mails enviados com status e timestamps.'},
};

function renderPainelSimples(n) {
  const info = ETAPAS_INFO[n];
  document.getElementById('painel').innerHTML = `
    <div class="painel-title">${info.titulo}</div>
    <div class="painel-desc">${info.desc}</div>
    <div class="btn-row">
      <button class="btn btn-primary" onclick="rodarEtapa(${n})">Executar Etapa ${n.toString().padStart(2,'0')}</button>
    </div>
  `;
}

/* ── Rodar Etapas via SSE ── */
function rodarEtapa(n) {
  document.getElementById('step-'+n).classList.remove('done','error','active');
  document.getElementById('step-'+n).classList.add('running');
  setBadge(n, 'running', 'Executando');
  abrirLog();
  limparLog();

  const es = new EventSource('/rodar/'+n);

  es.onmessage = (e) => appendLog(e.data);

  es.addEventListener('done', (e) => {
    es.close();
    const ok = e.data === 'ok';
    document.getElementById('step-'+n).classList.remove('running');
    document.getElementById('step-'+n).classList.add(ok ? 'done' : 'error');
    setBadge(n, ok ? 'done' : 'error', ok ? 'Concluído' : 'Erro');
    if (n === 2) carregarProspects();
  });

  es.onerror = () => {
    es.close();
    document.getElementById('step-'+n).classList.remove('running');
    document.getElementById('step-'+n).classList.add('error');
    setBadge(n, 'error', 'Falha de conexão');
  };
}

/* ── Log ── */
function abrirLog() {
  logAberto = true;
  document.getElementById('log-panel').classList.remove('log-hidden');
  document.getElementById('log-toggle').textContent = '▴ recolher';
}

function toggleLog() {
  logAberto = !logAberto;
  document.getElementById('log-panel').classList.toggle('log-hidden', !logAberto);
  document.getElementById('log-toggle').textContent = logAberto ? '▴ recolher' : '▾ expandir';
}

function limparLog() {
  document.getElementById('log').innerHTML = '';
}

function appendLog(txt) {
  const log = document.getElementById('log');
  const d = document.createElement('div');
  if (txt.includes('ERRO') || txt.includes('ERROR') || txt.includes('Erro')) d.className = 'err';
  else if (txt.includes('OK') || txt.includes('Concluído') || txt.includes('salvo') || txt.includes('→')) d.className = 'ok';
  else if (txt.startsWith('[Etapa') || txt.startsWith('Buscando')) d.className = 'info';
  d.textContent = txt;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}

/* ── Badges ── */
const BADGE_LABELS = {idle:'Aguardando', running:'Executando', done:'Concluído', error:'Erro'};
function setBadge(n, estado, label) {
  const b = document.getElementById('badge-'+n);
  if (!b) return;
  b.textContent = label || BADGE_LABELS[estado] || estado;
  // remove classes antigas
  b.parentElement.classList.remove('running','done','error');
  if (estado !== 'idle') b.parentElement.classList.add(estado);
}

/* ── Listas ── */
async function carregarListas() {
  const resp = await fetch('/listas');
  listasCache = await resp.json();
  renderListas();
  return listasCache;
}

function renderListas() {
  const grid = document.getElementById('listas-grid');
  if (!listasCache.length) {
    grid.innerHTML = '<div class="listas-vazio">Nenhuma lista salva ainda.</div>';
    return;
  }
  grid.innerHTML = listasCache.map(l => `
    <div class="lista-card">
      <div class="lista-nome">${esc(l.nome)}</div>
      <div class="lista-meta">${l.total} empresa(s) · ${formatarData(l.criado_em)}</div>
      <div class="lista-actions">
        <button class="btn btn-ghost btn-sm" onclick="usarLista('${l.id}')">Usar na Etapa 2</button>
        <button class="btn btn-danger" onclick="deletarLista('${l.id}')">Remover</button>
      </div>
    </div>
  `).join('');
}

async function deletarLista(id) {
  if (!confirm('Remover esta lista?')) return;
  await fetch('/listas/'+id, {method:'DELETE'});
  carregarListas();
}

function usarLista(id) {
  abrirStep(2);
  setTimeout(() => {
    const sel = document.getElementById('sel-lista');
    if (sel) { sel.value = id; selecionarFonte('lista'); }
  }, 100);
}

/* ── Prospects (para etapa 2+) ── */
async function carregarProspects() {
  // atualiza count no badge do step 2
  const resp = await fetch('/prospects');
  const lista = await resp.json();
  if (lista.length) setBadge(2, 'done', lista.length+' empresas');
}

/* ── Utils ── */
function esc(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function formatarData(iso) {
  if (!iso) return '';
  try { return new Date(iso).toLocaleDateString('pt-BR', {day:'2-digit',month:'2-digit',year:'numeric'}); }
  catch { return iso.slice(0,10); }
}

/* ── Init ── */
carregarListas();
carregarProspects();
// log começa recolhido
document.getElementById('log-panel').classList.add('log-hidden');
</script>
</body>
</html>"""


# ─── Rotas estáticas ──────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML


# ─── Busca com parâmetros (SSE) ───────────────────────────────────────────────

@app.get("/buscar/stream")
async def buscar_stream(
    segmento: str = "",
    cidade: str = "",
    porte: str = "",
    cnae: str = "",
    keywords: str = "",
):
    """Executa busca em thread e faz streaming dos resultados via SSE."""
    params = {
        "segmento": unquote(segmento),
        "cidade":   unquote(cidade),
        "porte":    unquote(porte),
        "cnae":     unquote(cnae),
        "keywords": unquote(keywords),
    }

    fila: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def _rodar():
        from etapas._01_busca import buscar_com_parametros

        def on_log(msg):
            asyncio.run_coroutine_threadsafe(
                fila.put(("msg", json.dumps({"t": "log", "m": msg}, ensure_ascii=False))), loop
            )

        def on_empresa(e):
            asyncio.run_coroutine_threadsafe(
                fila.put(("msg", json.dumps({"t": "empresa", "e": e}, ensure_ascii=False))), loop
            )

        try:
            buscar_com_parametros(params, on_log=on_log, on_empresa=on_empresa)
        except Exception as ex:
            asyncio.run_coroutine_threadsafe(
                fila.put(("msg", json.dumps({"t": "log", "m": f"ERRO: {ex}"}, ensure_ascii=False))), loop
            )
        finally:
            asyncio.run_coroutine_threadsafe(fila.put(("done", "ok")), loop)

    threading.Thread(target=_rodar, daemon=True).start()

    async def gerador():
        while True:
            tipo, dado = await fila.get()
            if tipo == "msg":
                yield f"data: {dado}\n\n"
            else:
                yield "event: done\ndata: ok\n\n"
                break

    return StreamingResponse(gerador(), media_type="text/event-stream")


# ─── Listas ───────────────────────────────────────────────────────────────────

@app.get("/listas")
async def listar_listas():
    return JSONResponse(ler_listas())


@app.post("/listas")
async def criar_lista(request: Request):
    body = await request.json()
    nome = body.get("nome", "").strip()
    empresas = body.get("empresas", [])
    if not nome or not empresas:
        return JSONResponse({"erro": "nome e empresas são obrigatórios"}, status_code=400)

    listas = ler_listas()
    nova = {
        "id": uuid.uuid4().hex[:10],
        "nome": nome,
        "criado_em": datetime.now().isoformat(),
        "total": len(empresas),
        "empresas": empresas,
    }
    listas.append(nova)
    salvar_listas(listas)
    return JSONResponse({"ok": True, "id": nova["id"]})


@app.delete("/listas/{lista_id}")
async def deletar_lista(lista_id: str):
    listas = [l for l in ler_listas() if l["id"] != lista_id]
    salvar_listas(listas)
    return JSONResponse({"ok": True})


# ─── Etapa 2 — preparar fonte de dados ───────────────────────────────────────

@app.post("/etapa2/preparar")
async def etapa2_preparar(request: Request):
    """Copia empresas de uma lista salva para prospects.json."""
    body = await request.json()
    lista_id = body.get("lista_id", "")

    listas = ler_listas()
    lista = next((l for l in listas if l["id"] == lista_id), None)
    if not lista:
        return JSONResponse({"erro": "lista não encontrada"}, status_code=404)

    ARQUIVO_PROSPECTS.parent.mkdir(exist_ok=True)
    ARQUIVO_PROSPECTS.write_text(
        json.dumps(lista["empresas"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return JSONResponse({"ok": True, "total": len(lista["empresas"])})


@app.post("/etapa2/upload")
async def etapa2_upload(file: UploadFile = File(...)):
    """Parseia CSV ou XML enviado e salva como prospects.json."""
    conteudo = await file.read()
    empresas = []

    if file.filename.endswith(".csv"):
        texto = conteudo.decode("utf-8-sig", errors="replace")
        # detecta separador
        sep = ";" if texto.count(";") > texto.count(",") else ","
        reader = csv.DictReader(io.StringIO(texto), delimiter=sep)
        for row in reader:
            # normaliza nomes de colunas
            row_lower = {k.lower().strip(): v for k, v in row.items() if k}
            empresas.append({
                "nome":     row_lower.get("nome") or row_lower.get("empresa") or "",
                "site":     row_lower.get("site") or row_lower.get("url") or row_lower.get("website") or "",
                "email":    row_lower.get("email") or "",
                "telefone": row_lower.get("telefone") or row_lower.get("phone") or "",
                "setor":    row_lower.get("setor") or row_lower.get("segmento") or "",
                "municipio": row_lower.get("municipio") or row_lower.get("cidade") or "",
                "aprovado": False,
            })

    elif file.filename.endswith(".xml"):
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(conteudo.decode("utf-8", errors="replace"))
            for emp in root.iter("empresa"):
                empresas.append({
                    "nome":     (emp.findtext("nome") or "").strip(),
                    "site":     (emp.findtext("site") or emp.findtext("url") or "").strip(),
                    "email":    (emp.findtext("email") or "").strip(),
                    "telefone": (emp.findtext("telefone") or "").strip(),
                    "setor":    (emp.findtext("setor") or emp.findtext("segmento") or "").strip(),
                    "municipio": (emp.findtext("municipio") or emp.findtext("cidade") or "").strip(),
                    "aprovado": False,
                })
        except ET.ParseError as e:
            return JSONResponse({"erro": f"XML inválido: {e}"}, status_code=400)
    else:
        return JSONResponse({"erro": "formato não suportado. Use .csv ou .xml"}, status_code=400)

    if not empresas:
        return JSONResponse({"erro": "nenhuma empresa encontrada no arquivo"}, status_code=400)

    ARQUIVO_PROSPECTS.parent.mkdir(exist_ok=True)
    ARQUIVO_PROSPECTS.write_text(
        json.dumps(empresas, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return JSONResponse({"ok": True, "total": len(empresas)})


# ─── Execução das etapas (SSE) ────────────────────────────────────────────────

def capturar_saida_etapa(etapa_num: int, loop: asyncio.AbstractEventLoop) -> asyncio.Queue:
    fila: asyncio.Queue = asyncio.Queue()

    def _rodar():
        import importlib
        import io as _io

        modulo_map = {
            1: "etapas._01_busca",
            2: "etapas._02_crawler",
            3: "etapas._03_analise",
            4: "etapas._04_apresentacao",
            5: "etapas._05_email",
            6: "etapas._06_auditoria",
        }
        buffer = _io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buffer
        resultado = "ok"
        try:
            mod = importlib.import_module(modulo_map[etapa_num])
            importlib.reload(mod)
            mod.executar()
        except Exception as e:
            resultado = f"erro: {e}"
        finally:
            sys.stdout = old_stdout

        for linha in buffer.getvalue().splitlines():
            asyncio.run_coroutine_threadsafe(fila.put(("msg", linha)), loop)
        asyncio.run_coroutine_threadsafe(fila.put(("done", resultado)), loop)

    threading.Thread(target=_rodar, daemon=True).start()
    return fila


@app.get("/rodar/{etapa}")
async def rodar_etapa(etapa: int):
    if etapa not in range(1, 7):
        return JSONResponse({"erro": "etapa inválida"}, status_code=400)

    loop = asyncio.get_event_loop()
    fila = capturar_saida_etapa(etapa, loop)

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


# ─── Prospects (legado — usado por etapas 3+) ────────────────────────────────

@app.get("/prospects")
async def listar_prospects():
    if not ARQUIVO_PROSPECTS.exists():
        return JSONResponse([])
    return JSONResponse(json.loads(ARQUIVO_PROSPECTS.read_text(encoding="utf-8")))


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
