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

from fastapi import FastAPI, Request, UploadFile, File, Form
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
  --bg:#FCEFC8;--s1:#F5E5A8;--s2:#EDDB8E;--bd:#D8C47A;--bd2:#C4AC5C;
  --t1:#0D0D0D;--t2:#4B585A;--t3:#6B7E80;--t4:#9AACAE;
  --ac:#001B72;--ac-light:#001B72;--ac2:#610713;--amber:#B07800;--green:#1a7a3a;--red:#610713;
}
html{scroll-behavior:smooth}
body{font-family:'PP','Helvetica Neue',sans-serif;background:var(--bg);color:var(--t1);font-size:15px;line-height:1.7;min-height:100vh}

/* ── TOPBAR ── */
.topbar{display:flex;align-items:center;justify-content:space-between;padding:18px 40px;border-bottom:1px solid var(--bd);position:sticky;top:0;background:rgba(252,239,200,.97);backdrop-filter:blur(14px);z-index:100}
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
.step.active .step-badge{color:var(--ac-light)}
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
.field input,.field select{width:100%;background:#fff;border:1px solid var(--bd2);border-radius:2px;padding:10px 14px;font-size:.93rem;font-family:'PP',sans-serif;color:var(--t1);outline:none;transition:border-color .15s}
.field input:focus,.field select:focus{border-color:var(--ac)}
.field input::placeholder{color:var(--t4)}
.field select option{background:#fff}

/* ── TAG INPUT ── */
.tag-input{width:100%;background:#fff;border:1px solid var(--bd2);border-radius:2px;min-height:46px;padding:6px 10px;display:flex;flex-wrap:wrap;gap:6px;align-items:center;cursor:text;transition:border-color .15s;box-sizing:border-box}
.tag-input:focus-within{border-color:var(--ac)}
.tag-chip{display:inline-flex;align-items:center;gap:6px;background:var(--ac);color:#fff;font-size:.78rem;font-family:'PP',sans-serif;padding:4px 10px 4px 12px;border-radius:2px;white-space:nowrap}
.tag-chip-remove{background:none;border:none;color:#fff;cursor:pointer;padding:0;line-height:1;font-size:1rem;opacity:.6;display:flex;align-items:center}
.tag-chip-remove:hover{opacity:1}
.tag-text-input{background:none;border:none;outline:none;color:var(--t1);font-size:.9rem;font-family:'PP',sans-serif;min-width:140px;flex:1;padding:2px 4px}
.tag-text-input::placeholder{color:var(--t4)}
.tag-hint{font-size:.68rem;color:var(--t4);margin-top:5px}

/* ── BUTTONS ── */
.btn{display:inline-flex;align-items:center;gap:8px;padding:10px 22px;font-size:.85rem;font-family:'PP',sans-serif;border-radius:2px;cursor:pointer;transition:all .15s;letter-spacing:.04em;border:none}
.btn-primary{background:var(--ac);color:#fff;font-weight:600}
.btn-primary:hover{background:#00257a}
.btn-primary:disabled{background:#8898c8;color:#c8d0e8;cursor:not-allowed}
.btn-ghost{background:transparent;border:1px solid var(--bd2);color:var(--t2)}
.btn-ghost:hover{border-color:var(--t3);color:var(--t1)}
.btn-danger{background:transparent;border:1px solid var(--ac2);color:var(--ac2);font-size:.78rem;padding:6px 12px}
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
.salvar-row input{flex:1;background:#fff;border:1px solid var(--bd2);border-radius:2px;padding:10px 14px;font-size:.9rem;font-family:'PP',sans-serif;color:var(--t1);outline:none}
.salvar-row input:focus{border-color:var(--ac)}

/* ── ETAPA 2 PAINEL ── */
.fonte-opcoes{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--bd);border:1px solid var(--bd);border-radius:2px;margin-bottom:24px}
.fonte-opcao{background:var(--s1);padding:24px;cursor:pointer;transition:background .15s}
.fonte-opcao.selected{background:var(--s2);outline:1px solid var(--ac-light)}
.fonte-opcao h4{font-size:.85rem;color:var(--t1);margin-bottom:4px}
.fonte-opcao p{font-size:.78rem;color:var(--t3);margin-bottom:16px;line-height:1.6}
.fonte-opcao select,.fonte-opcao input[type=file]{width:100%;background:#fff;border:1px solid var(--bd2);border-radius:2px;padding:9px 12px;font-size:.85rem;font-family:'PP',sans-serif;color:var(--t1);outline:none}
.fonte-opcao select:focus{border-color:var(--ac)}
.upload-hint{font-size:.72rem;color:var(--t4);margin-top:8px}

/* ── LOG ── */
.log-panel{background:var(--s1);border:1px solid var(--bd);border-radius:2px;margin-bottom:24px}
.log-header{display:flex;align-items:center;justify-content:space-between;padding:14px 20px;border-bottom:1px solid var(--bd);cursor:pointer}
.log-header h2{font-size:.7rem;letter-spacing:.16em;text-transform:uppercase;color:var(--t4)}
.log-toggle{font-size:.72rem;color:var(--t3)}
#log{font-family:'SF Mono','Fira Code','Courier New',monospace;font-size:.78rem;color:var(--t2);white-space:pre-wrap;max-height:240px;overflow-y:auto;line-height:1.75;padding:16px 20px}
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

/* ── LISTA ATIVA BANNER ── */
.lista-ativa-banner{display:none;align-items:center;justify-content:space-between;gap:16px;background:var(--ac);color:#fff;padding:10px 20px;border-radius:2px;margin-bottom:16px;flex-wrap:wrap}
.lista-ativa-left{display:flex;align-items:center;gap:10px}
.lista-ativa-label{font-size:.65rem;letter-spacing:.15em;text-transform:uppercase;opacity:.7}
.lista-ativa-nome{font-size:.9rem;font-weight:600}
.lista-ativa-total{font-size:.78rem;opacity:.75}
.lista-ativa-banner .btn-ghost{border-color:rgba(255,255,255,.4);color:#fff;font-size:.75rem;padding:5px 12px}
.lista-ativa-banner .btn-ghost:hover{border-color:#fff;background:rgba(255,255,255,.1)}

/* ── MODAL ── */
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.35);backdrop-filter:blur(4px);z-index:200;display:none;align-items:center;justify-content:center}
.modal-overlay.open{display:flex}
.modal-box{background:var(--bg);border:1px solid var(--bd);border-radius:2px;padding:32px;width:100%;max-width:440px;box-shadow:0 20px 60px rgba(0,0,0,.15)}
.modal-title{font-size:1rem;color:var(--t1);margin-bottom:6px}
.modal-desc{font-size:.85rem;color:var(--t2);margin-bottom:24px;line-height:1.6}

/* ── PAINEL LISTA INFO ── */
.painel-lista-info{display:flex;align-items:center;gap:10px;background:var(--s2);border:1px solid var(--bd);border-radius:2px;padding:10px 16px;margin-bottom:24px;font-size:.83rem;color:var(--t2)}
.painel-lista-info strong{color:var(--t1)}
.painel-lista-info .trocar-link{margin-left:auto;font-size:.75rem;color:var(--ac);cursor:pointer;text-decoration:underline;white-space:nowrap}

/* ── DIVISOR ── */
.divisor{display:flex;align-items:center;gap:12px;color:var(--t4);font-size:.78rem;margin:4px 0}
.divisor::before,.divisor::after{content:'';flex:1;height:1px;background:var(--bd)}

/* ── ANALISE CARDS ── */
.analise-card{background:var(--s2);border:1px solid var(--bd);border-radius:2px;padding:20px 24px;margin-bottom:12px}
.analise-card-header{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:14px}
.analise-card-nome{font-size:.95rem;color:var(--t1)}
.prioridade-badge{font-size:.65rem;letter-spacing:.12em;text-transform:uppercase;padding:3px 10px;border-radius:2px;white-space:nowrap;font-weight:600}
.prioridade-badge.alta{background:#001B72;color:#fff}
.prioridade-badge.media{background:#4B585A;color:#fff}
.prioridade-badge.baixa{background:var(--bd2);color:var(--t2)}
.analise-fields{display:grid;grid-template-columns:1fr 1fr;gap:10px 20px;margin-bottom:14px}
.analise-field label{font-size:.65rem;text-transform:uppercase;letter-spacing:.1em;color:var(--t3);display:block;margin-bottom:3px}
.analise-field p{font-size:.83rem;color:var(--t2);line-height:1.6}
.analise-field.full{grid-column:1/-1}
.analise-card-texto{font-size:.85rem;color:var(--t2);line-height:1.75;white-space:pre-wrap;border-top:1px solid var(--bd);padding-top:14px;margin-top:4px}
.analise-pessoa{font-size:.82rem;color:var(--t2);background:var(--bg);border:1px solid var(--bd);border-radius:2px;padding:8px 12px;margin-bottom:10px;display:flex;gap:16px;flex-wrap:wrap}
.analise-pessoa span{display:flex;flex-direction:column;gap:2px}
.analise-pessoa small{font-size:.65rem;text-transform:uppercase;letter-spacing:.08em;color:var(--t3)}

/* ── EMAIL PANEL ── */
.email-tabela-wrapper{overflow-x:auto;margin:20px 0}
.email-tabela{width:100%;border-collapse:collapse}
.email-tabela th{font-size:.68rem;text-transform:uppercase;letter-spacing:.1em;color:var(--t3);padding:10px 12px;border-bottom:1px solid var(--bd);text-align:left;white-space:nowrap}
.email-tabela td{padding:10px 12px;border-bottom:1px solid var(--bd);vertical-align:middle;color:var(--t2)}
.email-input-email{background:#fff;border:1px solid var(--bd2);border-radius:2px;padding:6px 10px;font-size:.83rem;font-family:'PP',sans-serif;color:var(--t1);outline:none;width:100%;min-width:180px}
.email-input-email:focus{border-color:var(--ac)}
.corpo-email-wrap{margin:20px 0}
.corpo-email-wrap label{font-size:.73rem;text-transform:uppercase;letter-spacing:.1em;color:var(--t3);display:block;margin-bottom:7px}
.corpo-email-wrap textarea{width:100%;background:#fff;border:1px solid var(--bd2);border-radius:2px;padding:12px 14px;font-size:.88rem;font-family:'PP',sans-serif;color:var(--t1);outline:none;resize:vertical;min-height:180px;line-height:1.7}
.corpo-email-wrap textarea:focus{border-color:var(--ac)}
.status-badge{font-size:.75rem;padding:3px 10px;border-radius:2px;display:inline-block}
.status-badge.ok{background:#c8ecd4;color:#1a5a2a}
.status-badge.erro{background:#f0d4d4;color:var(--ac2)}
.status-badge.enviando{background:#d4daf5;color:var(--ac)}

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
  <img src="/static/logo-dark.png" alt="BLOCO.">
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

  <!-- Banner lista ativa -->
  <div class="lista-ativa-banner" id="lista-ativa-banner">
    <div class="lista-ativa-left">
      <span class="lista-ativa-label">Lista ativa</span>
      <span class="lista-ativa-nome" id="lista-ativa-nome">—</span>
      <span class="lista-ativa-total" id="lista-ativa-total"></span>
    </div>
    <button class="btn btn-ghost" onclick="abrirTrocarLista()">↕ Trocar lista</button>
  </div>

  <!-- Painel dinâmico -->
  <div class="painel" id="painel"></div>

  <!-- Modal trocar lista -->
  <div class="modal-overlay" id="modal-overlay" onclick="fecharModal()">
    <div class="modal-box" onclick="event.stopPropagation()">
      <div class="modal-title">Trocar lista ativa</div>
      <div class="modal-desc">A lista escolhida será usada em todas as próximas etapas desta sessão.</div>
      <div class="field" style="margin-bottom:24px">
        <label>Selecione a lista</label>
        <select id="modal-sel-lista"></select>
      </div>
      <div class="btn-row">
        <button class="btn btn-primary" onclick="confirmarTrocarLista()">Confirmar</button>
        <button class="btn btn-ghost" onclick="fecharModal()">Cancelar</button>
      </div>
    </div>
  </div>

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
let listaAtiva = null; // {id, nome, total, empresas:[]}

/* ── Lista Ativa ── */
function setListaAtiva(lista) {
  listaAtiva = lista;
  const banner = document.getElementById('lista-ativa-banner');
  if (!lista) { banner.style.display = 'none'; return; }
  banner.style.display = 'flex';
  document.getElementById('lista-ativa-nome').textContent = lista.nome;
  document.getElementById('lista-ativa-total').textContent = '— ' + lista.total + ' empresa(s)';
}

function listaAtivaInfo() {
  if (!listaAtiva) return `<div class="painel-lista-info" style="background:#fff3cd;border-color:#d4a800">
    Nenhuma lista ativa. <span class="trocar-link" onclick="abrirStep(2)">Escolher lista na Etapa 2 →</span></div>`;
  return `<div class="painel-lista-info">
    <strong>${esc(listaAtiva.nome)}</strong>&nbsp;·&nbsp;${listaAtiva.total} empresa(s)
    <span class="trocar-link" onclick="abrirTrocarLista()">Não usar mais essa lista</span>
  </div>`;
}

async function abrirTrocarLista() {
  await carregarListas();
  const sel = document.getElementById('modal-sel-lista');
  sel.innerHTML = listasCache.map(l =>
    `<option value="${l.id}"${listaAtiva && l.id===listaAtiva.id?' selected':''}>${esc(l.nome)} (${l.total} emp.)</option>`
  ).join('');
  if (!listasCache.length) { sel.innerHTML = '<option disabled>Nenhuma lista salva</option>'; }
  document.getElementById('modal-overlay').classList.add('open');
}

function fecharModal() {
  document.getElementById('modal-overlay').classList.remove('open');
}

async function confirmarTrocarLista() {
  const sel = document.getElementById('modal-sel-lista');
  if (!sel.value) return;
  const lista = listasCache.find(l => l.id === sel.value);
  if (!lista) return;
  const resp = await fetch('/etapa2/preparar', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({lista_id: lista.id})
  });
  if (!resp.ok) { alert('Erro ao trocar lista.'); return; }
  setListaAtiva(lista);
  fecharModal();
  if (stepAtivo) abrirStep(stepAtivo);
}

/* ── Tag Input ── */
const tagState = {};

function initTagInput(id, placeholder) {
  const container = document.getElementById('tag-' + id);
  if (!container) return;
  tagState[id] = [];

  const inp = document.createElement('input');
  inp.className = 'tag-text-input';
  inp.placeholder = placeholder;
  inp.setAttribute('data-tag-id', id);
  container.appendChild(inp);

  inp.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTag(id, inp.value);
    } else if (e.key === 'Backspace' && inp.value === '' && tagState[id].length) {
      tagState[id].pop();
      renderTags(id);
    }
  });
  inp.addEventListener('blur', () => { if (inp.value.trim()) addTag(id, inp.value); });
}

function focusTag(id) {
  const inp = document.querySelector(`#tag-${id} .tag-text-input`);
  if (inp) inp.focus();
}

function addTag(id, raw) {
  raw.split(',').map(v => v.trim()).filter(Boolean).forEach(val => {
    if (!tagState[id].includes(val)) tagState[id].push(val);
  });
  renderTags(id);
  const inp = document.querySelector(`#tag-${id} .tag-text-input`);
  if (inp) inp.value = '';
}

function removeTag(id, idx) {
  tagState[id].splice(idx, 1);
  renderTags(id);
}

function renderTags(id) {
  const container = document.getElementById('tag-' + id);
  container.querySelectorAll('.tag-chip').forEach(c => c.remove());
  const inp = container.querySelector('.tag-text-input');
  tagState[id].forEach((tag, i) => {
    const chip = document.createElement('span');
    chip.className = 'tag-chip';
    chip.innerHTML = `${tag} <button class="tag-chip-remove" onclick="removeTag('${id}',${i})">×</button>`;
    container.insertBefore(chip, inp);
  });
  inp.placeholder = tagState[id].length ? '' : (id === 'segmento' ? 'Ex: advocacia, clínica médica…' : 'Ex: Porto Alegre, Curitiba…');
}

function getTagValues(id) {
  return tagState[id] ? [...tagState[id]] : [];
}

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
  else if (n === 3) renderPainel3();
  else if (n === 4) renderPainel4();
  else if (n === 5) renderPainel5();
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
        <div class="tag-input" id="tag-segmento" onclick="focusTag('segmento')"></div>
        <div class="tag-hint">Digite e pressione Enter ou vírgula para adicionar</div>
      </div>
      <div class="field">
        <label>Cidade / Região</label>
        <div class="tag-input" id="tag-cidade" onclick="focusTag('cidade')"></div>
        <div class="tag-hint">Digite e pressione Enter ou vírgula para adicionar</div>
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
  initTagInput('segmento', 'Ex: advocacia, clínica médica…');
  initTagInput('cidade', 'Ex: Porto Alegre, Curitiba…');
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
    segmento: getTagValues('segmento').join(','),
    cidade:   getTagValues('cidade').join(','),
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
    if (!resp.ok) { const err = await resp.json(); alert('Erro: ' + (err.erro || 'lista não encontrada.')); return; }
    const lista = listasCache.find(l => l.id === listaId);
    if (lista) setListaAtiva(lista);
  } else {
    const file = document.getElementById('input-upload').files[0];
    if (!file) { alert('Selecione um arquivo.'); return; }
    const form = new FormData();
    form.append('file', file);
    const resp = await fetch('/etapa2/upload', {method:'POST', body:form});
    if (!resp.ok) { alert('Erro ao processar arquivo.'); return; }
    const data = await resp.json();
    setListaAtiva({id:'_upload', nome: file.name, total: data.total || '?', empresas:[]});
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

/* ── Painel Etapa 3 ── */
function renderPainel3() {
  document.getElementById('painel').innerHTML = `
    <div class="painel-title">Analisar com IA</div>
    ${listaAtivaInfo()}
    <div class="painel-desc">A API da Anthropic analisa cada empresa e identifica oportunidades audiovisuais personalizadas.</div>
    <div class="btn-row">
      <button class="btn btn-primary" onclick="rodarEtapa(3, carregarAnalises)">Executar Etapa 03</button>
    </div>
    <div id="analises-resultado"></div>
  `;
  carregarAnalises();
}

/* ── Painel Etapa 4 ── */
function renderPainel4() {
  document.getElementById('painel').innerHTML = `
    <div class="painel-title">Gerar Apresentações</div>
    ${listaAtivaInfo()}
    <div class="painel-desc">Cria um documento .md personalizado por empresa com análise, bio da Bloco Produções e plano de ação. Salvo em /apresentacoes/.</div>
    <div class="btn-row">
      <button class="btn btn-primary" onclick="rodarEtapa(4)">Executar Etapa 04</button>
    </div>
  `;
}

function renderAnaliseCard(a) {
  const prio = (a.prioridade || '').toLowerCase().replace('é','e');
  const prioLabel = a.prioridade || '—';
  const pessoaHtml = (a.pessoa_chave || a.cargo || a.linkedin_contato) ? `
    <div class="analise-pessoa">
      ${a.pessoa_chave ? `<span><small>Pessoa-chave</small>${esc(a.pessoa_chave)}</span>` : ''}
      ${a.cargo ? `<span><small>Cargo</small>${esc(a.cargo)}</span>` : ''}
      ${a.linkedin_contato ? `<span><small>LinkedIn / Contato</small><a href="${esc(a.linkedin_contato)}" target="_blank" style="color:var(--ac);font-size:.8rem">${esc(a.linkedin_contato.replace('https://','').slice(0,50))}</a></span>` : ''}
    </div>` : '';
  return `<div class="analise-card">
    <div class="analise-card-header">
      <div class="analise-card-nome">${esc(a.empresa)}</div>
      <span class="prioridade-badge ${prio}">${prioLabel}</span>
    </div>
    ${pessoaHtml}
    <div class="analise-fields">
      ${a.por_que_oportunidade ? `<div class="analise-field full"><label>Por que é uma oportunidade</label><p>${esc(a.por_que_oportunidade)}</p></div>` : ''}
      ${a.dor_provavel ? `<div class="analise-field"><label>Dor provável</label><p>${esc(a.dor_provavel)}</p></div>` : ''}
      ${a.servico_bloco ? `<div class="analise-field"><label>Serviço Bloco relevante</label><p>${esc(a.servico_bloco)}</p></div>` : ''}
      ${a.abordagem_sugerida ? `<div class="analise-field full"><label>Abordagem sugerida</label><p>${esc(a.abordagem_sugerida)}</p></div>` : ''}
    </div>
    ${a.analise ? `<div class="analise-card-texto">${esc(a.analise)}</div>` : ''}
  </div>`;
}

async function carregarAnalises() {
  const div = document.getElementById('analises-resultado');
  if (!div) return;
  try {
    const resp = await fetch('/analises');
    if (!resp.ok) { div.innerHTML = '<p style="color:var(--red);font-size:.85rem;margin-top:20px">Erro ao carregar análises.</p>'; return; }
    const analises = await resp.json();
    if (!analises.length) { div.innerHTML = '<p style="color:var(--t4);font-size:.85rem;margin-top:20px">Nenhuma análise disponível. Execute a etapa para gerar resultados.</p>'; return; }
    const alta  = analises.filter(a => a.prioridade === 'Alta').length;
    const media = analises.filter(a => a.prioridade === 'Média').length;
    const baixa = analises.filter(a => a.prioridade === 'Baixa').length;
    const header = `<div style="display:flex;gap:16px;align-items:center;margin-top:28px;margin-bottom:16px;flex-wrap:wrap">
      <div style="font-size:.7rem;letter-spacing:.15em;text-transform:uppercase;color:var(--t3)">${analises.length} empresa(s) analisada(s)</div>
      ${alta  ? `<span class="prioridade-badge alta">Alta: ${alta}</span>` : ''}
      ${media ? `<span class="prioridade-badge media">Média: ${media}</span>` : ''}
      ${baixa ? `<span class="prioridade-badge baixa">Baixa: ${baixa}</span>` : ''}
    </div>`;
    div.innerHTML = header + analises.map(renderAnaliseCard).join('');
  } catch(e) {
    div.innerHTML = '<p style="color:var(--red);font-size:.85rem;margin-top:20px">Erro ao carregar análises: ' + e.message + '</p>';
  }
}

/* ── Painel Etapa 5 ── */
let empresasEmail = [];

function renderPainel5() {
  const corpoDefault = `Olá!\n\nMeu nome é [SEU NOME] e faço parte da equipe da Bloco Produções, produtora audiovisual do Sul do Brasil.\n\nEstudei um pouco sobre a {empresa} e acredito que temos ideias interessantes de como a comunicação audiovisual pode amplificar a presença de vocês — seja com vídeo institucional, reels, cases ou conteúdo para redes sociais.\n\nPreparei uma apresentação personalizada que está em anexo.\n\nFico à disposição!\n\nAtenciosamente,\n[SEU NOME] — Bloco Produções`;
  document.getElementById('painel').innerHTML = `
    <div class="painel-title">Enviar E-mails</div>
    ${listaAtivaInfo()}
    <div class="painel-desc">Personalize o texto e anexe a apresentação em PDF para cada empresa.</div>
    <div class="corpo-email-wrap">
      <label>Texto do e-mail</label>
      <textarea id="corpo-email">${corpoDefault}</textarea>
    </div>
    <div id="empresas-email"></div>
    <div id="status-envios"></div>
  `;
  if (listaAtiva && listaAtiva.id !== '_upload' && listaAtiva.empresas && listaAtiva.empresas.length) {
    empresasEmail = listaAtiva.empresas;
    renderTabelaEmail();
  } else if (listaAtiva) {
    carregarEmpresasEmail(listaAtiva.id);
  }
}

function renderTabelaEmail() {
  const div = document.getElementById('empresas-email');
  if (!div) return;
  if (!empresasEmail.length) { div.innerHTML = '<p style="color:var(--t4);font-size:.85rem">Nenhuma empresa nesta lista.</p>'; return; }
  div.innerHTML = `
    <div class="email-tabela-wrapper">
      <table class="email-tabela">
        <thead><tr>
          <th style="width:36px"></th>
          <th>Empresa</th>
          <th>E-mail</th>
          <th>Apresentação PDF</th>
          <th>Ação</th>
        </tr></thead>
        <tbody>
          ${empresasEmail.map((e, i) => `
            <tr id="email-row-${i}">
              <td><div class="cb-wrap"><input type="checkbox" checked id="cb-email-${i}"></div></td>
              <td>${esc(e.nome)}</td>
              <td><input class="email-input-email" type="email" id="email-dest-${i}" value="${esc(e.email||'')}"></td>
              <td><input type="file" accept=".pdf" id="pdf-${i}"></td>
              <td id="acao-${i}"><button class="btn btn-ghost btn-sm" onclick="enviarEmailEmpresa(${i})">Enviar</button></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
    <div class="btn-row" style="margin-top:12px">
      <button class="btn btn-primary" onclick="enviarTodasSelecionadas()">Enviar para todas selecionadas</button>
    </div>
  `;
}

async function carregarEmpresasEmail(listaId) {
  if (!listaId || listaId === '_upload') {
    const resp = await fetch('/prospects');
    empresasEmail = await resp.json();
  } else {
    const resp = await fetch('/listas');
    const listas = await resp.json();
    const lista = listas.find(l => l.id === listaId);
    if (!lista) { return; }
    empresasEmail = lista.empresas;
  }
  renderTabelaEmail();
}

async function enviarEmailEmpresa(idx) {
  const emp = empresasEmail[idx];
  const emailInput = document.getElementById('email-dest-'+idx);
  const corpo = document.getElementById('corpo-email').value;
  const pdfInput = document.getElementById('pdf-'+idx);
  const acaoCell = document.getElementById('acao-'+idx);

  acaoCell.innerHTML = '<span class="status-badge enviando">Enviando…</span>';

  const form = new FormData();
  form.append('empresa', JSON.stringify(emp));
  form.append('corpo', corpo);
  if (pdfInput.files[0]) form.append('pdf', pdfInput.files[0]);

  try {
    const resp = await fetch('/etapa5/enviar-empresa', {method:'POST', body:form});
    const data = await resp.json();
    if (resp.ok && data.ok) {
      acaoCell.innerHTML = '<span class="status-badge ok">Enviado</span>';
    } else {
      acaoCell.innerHTML = `<span class="status-badge erro" title="${esc(data.erro||'')}">Erro</span>`;
    }
  } catch(e) {
    acaoCell.innerHTML = '<span class="status-badge erro">Falha</span>';
  }
}

async function enviarTodasSelecionadas() {
  for (let i = 0; i < empresasEmail.length; i++) {
    const cb = document.getElementById('cb-email-'+i);
    if (cb && cb.checked) {
      await enviarEmailEmpresa(i);
      await new Promise(r => setTimeout(r, 500));
    }
  }
}

/* ── Rodar Etapas via SSE ── */
function rodarEtapa(n, onDone) {
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
    if (ok && typeof onDone === 'function') onDone();
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

class _StreamWriter:
    """Substitui sys.stdout e envia cada linha ao SSE em tempo real."""
    def __init__(self, fila: asyncio.Queue, loop: asyncio.AbstractEventLoop):
        self._fila = fila
        self._loop = loop
        self._buf = ""

    def write(self, text: str):
        self._buf += text
        while "\n" in self._buf:
            linha, self._buf = self._buf.split("\n", 1)
            if linha:
                asyncio.run_coroutine_threadsafe(
                    self._fila.put(("msg", linha)), self._loop
                )

    def flush(self):
        if self._buf.strip():
            asyncio.run_coroutine_threadsafe(
                self._fila.put(("msg", self._buf)), self._loop
            )
            self._buf = ""


def capturar_saida_etapa(etapa_num: int, loop: asyncio.AbstractEventLoop) -> asyncio.Queue:
    fila: asyncio.Queue = asyncio.Queue()

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
        old_stdout = sys.stdout
        sys.stdout = _StreamWriter(fila, loop)
        resultado = "ok"
        try:
            mod = importlib.import_module(modulo_map[etapa_num])
            importlib.reload(mod)
            mod.executar()
        except Exception as e:
            resultado = f"erro: {e}"
        finally:
            sys.stdout.flush()
            sys.stdout = old_stdout

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


@app.get("/analises")
async def listar_analises():
    arq = Path("dados/analyses.json")
    if not arq.exists():
        return JSONResponse([])
    return JSONResponse(json.loads(arq.read_text(encoding="utf-8")))


@app.post("/etapa5/enviar-empresa")
async def etapa5_enviar_empresa(
    empresa: str = Form(...),
    corpo: str = Form(...),
    pdf: UploadFile = File(None),
):
    """Envia e-mail para uma empresa com texto customizado e PDF opcional."""
    import base64
    from email.mime.application import MIMEApplication
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    emp = json.loads(empresa)
    nome = emp.get("nome", "")
    email_dest = emp.get("email", "")

    if not email_dest:
        return JSONResponse({"erro": "empresa sem e-mail"}, status_code=400)

    remetente = os.getenv("GMAIL_REMETENTE", "")
    if not remetente:
        return JSONResponse({"erro": "GMAIL_REMETENTE não configurado"}, status_code=500)

    msg = MIMEMultipart()
    msg["to"] = email_dest
    msg["from"] = remetente
    assunto = f"Uma ideia para {nome} — Bloco Produções"
    msg["subject"] = assunto
    msg.attach(MIMEText(corpo, "plain", "utf-8"))

    if pdf and pdf.filename:
        conteudo_pdf = await pdf.read()
        parte = MIMEApplication(conteudo_pdf, Name=pdf.filename)
        parte["Content-Disposition"] = f'attachment; filename="{pdf.filename}"'
        msg.attach(parte)

    try:
        from etapas._05_email import autenticar_gmail
        servico = autenticar_gmail()
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        servico.users().messages().send(userId="me", body={"raw": raw}).execute()

        entrada = {"empresa": nome, "email": email_dest, "timestamp": datetime.now().isoformat(), "status": "enviado"}
        arq_log = Path("dados/audit_log.json")
        log = json.loads(arq_log.read_text(encoding="utf-8")) if arq_log.exists() else []
        log.append(entrada)
        arq_log.parent.mkdir(exist_ok=True)
        arq_log.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"erro": str(e)}, status_code=500)


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
