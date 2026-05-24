"""
Etapa 4 — Geração de apresentações personalizadas em HTML.

Para cada empresa com análise, gera uma apresentação HTML estilizada
com a identidade visual da Bloco Produções.
Salva em apresentacoes/{slug}.html — abre no navegador, exportável como PDF.
"""

import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from etapas._utils import nome_para_arquivo

load_dotenv()

ARQUIVO_PROSPECTS = Path("dados/prospects.json")
ARQUIVO_ANALISES  = Path("dados/analyses.json")
PASTA_SAIDA       = Path("apresentacoes")

BLOCO_BIO = os.getenv(
    "BLOCO_BIO",
    "A Bloco Produções é um estúdio criativo e estratégico especializado em produção "
    "audiovisual: vídeos institucionais, reels, cases de sucesso, calendários editoriais "
    "e conteúdo para redes sociais. Atende marcas que precisam escalar presença digital "
    "com produção recorrente e consistente.",
)

# ─── Template HTML ─────────────────────────────────────────────────────────────

def _html(empresa: dict, analise_dados: dict, plano: list[str], hoje: str) -> str:
    nome          = empresa.get("nome", "")
    setor         = empresa.get("setor") or empresa.get("setor_receita", "")
    municipio     = empresa.get("municipio", "")
    pessoa_chave  = analise_dados.get("pessoa_chave", "")
    cargo         = analise_dados.get("cargo", "")
    prioridade    = analise_dados.get("prioridade", "")
    dor           = analise_dados.get("dor_provavel", "")
    servico       = analise_dados.get("servico_bloco", "")
    abordagem     = analise_dados.get("abordagem_sugerida", "")
    analise_texto = analise_dados.get("analise", "") or analise_dados.get("por_que_oportunidade", "")

    destinatario = pessoa_chave or "Prezado(a) responsável"
    cargo_str    = f" — {cargo}" if cargo else ""

    plano_html = "\n".join(f"<li>{item.lstrip('- ').strip()}</li>" for item in plano if item.strip())

    def p(text: str) -> str:
        """Converte texto com quebras de linha em parágrafos HTML."""
        if not text:
            return ""
        return "".join(f"<p>{line}</p>" for line in text.split("\n") if line.strip())

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bloco Produções — {nome}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
<style>
@import url('https://fonts.cdnfonts.com/css/pp-telegraf');
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#FCEFC8;--s1:#F5E5A8;--s2:#EDDB8E;--bd:#D8C47A;
  --t1:#0D0D0D;--t2:#4B585A;--t3:#6B7E80;
  --ac:#001B72;--ac2:#610713;
}}
body{{font-family:'PP Telegraf','Helvetica Neue',sans-serif;background:var(--bg);
  color:var(--t1);font-size:15px;line-height:1.75;min-height:100vh}}

/* CAPA */
.capa{{background:var(--ac);color:#fff;padding:60px 64px 48px;position:relative;overflow:hidden}}
.capa::after{{content:'';position:absolute;bottom:-60px;right:-60px;width:280px;height:280px;
  border-radius:50%;background:rgba(255,255,255,.06)}}
.capa-label{{font-size:.68rem;letter-spacing:.2em;text-transform:uppercase;opacity:.65;margin-bottom:20px}}
.capa-nome{{font-size:2.4rem;line-height:1.15;margin-bottom:8px;font-weight:400}}
.capa-sub{{font-size:1rem;opacity:.75;margin-bottom:32px}}
.capa-meta{{display:flex;gap:24px;flex-wrap:wrap;font-size:.78rem;opacity:.6;border-top:1px solid rgba(255,255,255,.2);padding-top:20px}}
.badge-prio{{display:inline-block;font-size:.65rem;letter-spacing:.12em;text-transform:uppercase;
  padding:4px 12px;border-radius:2px;background:rgba(255,255,255,.15);color:#fff;margin-bottom:16px}}

/* CONTEÚDO */
.page{{max-width:760px;margin:0 auto;padding:56px 40px 80px}}
section{{margin-bottom:48px}}
.sec-label{{font-size:.65rem;letter-spacing:.2em;text-transform:uppercase;color:var(--t3);
  margin-bottom:16px;display:flex;align-items:center;gap:10px}}
.sec-label::after{{content:'';flex:1;height:1px;background:var(--bd)}}
h2{{font-size:1.15rem;color:var(--t1);margin-bottom:16px;font-weight:400}}
p{{color:var(--t2);margin-bottom:12px;font-size:.93rem}}
p:last-child{{margin-bottom:0}}

/* CARDS DE INFO */
.info-grid{{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--bd);
  border:1px solid var(--bd);border-radius:2px;margin-bottom:32px}}
.info-cell{{background:var(--s1);padding:16px 20px}}
.info-cell label{{font-size:.63rem;letter-spacing:.15em;text-transform:uppercase;
  color:var(--t3);display:block;margin-bottom:5px}}
.info-cell p{{font-size:.88rem;color:var(--t1);margin:0}}

/* PLANO DE AÇÃO */
.plano-list{{list-style:none;display:flex;flex-direction:column;gap:12px}}
.plano-list li{{background:var(--s1);border-left:3px solid var(--ac);
  padding:14px 18px;border-radius:0 2px 2px 0;font-size:.9rem;color:var(--t2)}}

/* ABORDAGEM */
.abordagem-box{{background:var(--ac);color:#fff;padding:24px 28px;border-radius:2px}}
.abordagem-box p{{color:rgba(255,255,255,.85);font-size:.9rem}}

/* RODAPÉ */
footer{{background:var(--t1);color:var(--bg);padding:40px 64px;font-size:.82rem;letter-spacing:.04em}}
footer .footer-grid{{display:grid;grid-template-columns:1fr 1fr;gap:24px 48px;max-width:560px}}
footer .footer-item label{{font-size:.6rem;letter-spacing:.15em;text-transform:uppercase;opacity:.5;display:block;margin-bottom:4px}}
footer .footer-item a,footer .footer-item span{{color:#fff;text-decoration:none}}
footer .footer-bottom{{margin-top:28px;padding-top:20px;border-top:1px solid rgba(255,255,255,.12);font-size:.72rem;opacity:.45}}

/* BOTÃO PDF */
.btn-pdf{{position:fixed;bottom:28px;right:28px;background:var(--ac);color:#fff;border:none;
  padding:12px 22px;border-radius:2px;font-size:.82rem;font-family:'PP Telegraf','Helvetica Neue',sans-serif;
  cursor:pointer;letter-spacing:.06em;box-shadow:0 4px 20px rgba(0,0,0,.2);z-index:999;
  display:flex;align-items:center;gap:8px}}
.btn-pdf:hover{{background:#00257a}}
.btn-pdf svg{{width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:2}}

/* PRINT */
@media print{{
  .capa,.abordagem-box,footer{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
  .btn-pdf{{display:none}}
  body{{font-size:13px}}
}}
</style>
</head>
<body>

<button class="btn-pdf" onclick="baixarPDF()" id="btn-pdf">
  <svg viewBox="0 0 24 24"><path d="M12 16l-4-4h3V4h2v8h3l-4 4z"/><path d="M4 18h16v2H4z"/></svg>
  Baixar PDF
</button>

<div id="conteudo-apresentacao">

<div class="capa">
  <div class="capa-label">Apresentação Personalizada — Bloco Produções</div>
  {f'<div class="badge-prio">{prioridade}</div>' if prioridade else ''}
  <div class="capa-nome">{nome}</div>
  <div class="capa-sub">{setor}{f' · {municipio}' if municipio else ''}</div>
  <div class="capa-meta">
    <span>Para: {destinatario}{cargo_str}</span>
    <span>Data: {hoje}</span>
    <span>Bloco Produções · comercial@blocoproducoes.com</span>
  </div>
</div>

<div class="page">

  <section>
    <div class="sec-label">Quem somos</div>
    {p(BLOCO_BIO)}
  </section>

  <section>
    <div class="sec-label">Análise</div>
    {p(analise_texto)}
  </section>

  {"" if not (dor or servico) else f'''
  <section>
    <div class="sec-label">Diagnóstico</div>
    <div class="info-grid">
      {"" if not dor else f'<div class="info-cell"><label>Dor identificada</label><p>{dor}</p></div>'}
      {"" if not servico else f'<div class="info-cell"><label>Solução Bloco</label><p>{servico}</p></div>'}
    </div>
  </section>
  '''}

  <section>
    <div class="sec-label">Plano de Ação</div>
    <ul class="plano-list">{plano_html}</ul>
  </section>

  {"" if not abordagem else f'''
  <section>
    <div class="sec-label">Abordagem Sugerida</div>
    <div class="abordagem-box">{p(abordagem)}</div>
  </section>
  '''}

</div>

<footer>
  <div class="footer-grid">
    <div class="footer-item">
      <label>WhatsApp</label>
      <a href="https://wa.me/5541984993028">(41) 98499-3028</a>
    </div>
    <div class="footer-item">
      <label>E-mail</label>
      <a href="mailto:comercial@blocoproducoes.com">comercial@blocoproducoes.com</a>
    </div>
    <div class="footer-item">
      <label>Instagram</label>
      <a href="https://instagram.com/bloco.studios" target="_blank">@bloco.studios</a>
    </div>
    <div class="footer-item">
      <label>Diretor de Operações</label>
      <span>Matheus Gobbi</span>
    </div>
  </div>
  <div class="footer-bottom">Bloco Produções · Apresentação gerada em {hoje} · Confidencial</div>
</footer>

</div><!-- /conteudo-apresentacao -->

<script>
function baixarPDF() {{
  const btn = document.getElementById('btn-pdf');
  btn.textContent = 'Gerando…';
  btn.disabled = true;
  const el = document.getElementById('conteudo-apresentacao');
  const opt = {{
    margin: 0,
    filename: '{nome.replace("'", "").replace('"', '')}.pdf',
    image: {{type:'jpeg', quality:0.95}},
    html2canvas: {{scale:2, useCORS:true, logging:false}},
    jsPDF: {{unit:'mm', format:'a4', orientation:'portrait'}},
    pagebreak: {{mode:['avoid-all','css','legacy']}},
  }};
  html2pdf().set(opt).from(el).save().then(() => {{
    btn.textContent = 'Baixar PDF';
    btn.disabled = false;
  }});
}}

// auto-download se ?pdf=1 na URL
if (new URLSearchParams(window.location.search).get('pdf') === '1') {{
  window.addEventListener('load', () => setTimeout(baixarPDF, 800));
}}
</script>
</body>
</html>"""


# ─── Geração do plano de ação ──────────────────────────────────────────────────

def gerar_plano(cliente: anthropic.Anthropic, nome: str, analise_dados: dict) -> list[str]:
    analise = analise_dados.get("analise", "") or analise_dados.get("por_que_oportunidade", "")
    dor      = analise_dados.get("dor_provavel", "")
    servico  = analise_dados.get("servico_bloco", "")

    resp = cliente.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=350,
        system=[{
            "type": "text",
            "text": (
                "Você é um especialista em marketing audiovisual da Bloco Produções. "
                "Gere exatamente 3 bullet points de plano de ação concreto e específico. "
                "Cada item começa com '- '. Sem introdução, sem numeração, sem texto extra."
            ),
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": (
                f"Empresa: {nome}\n"
                f"Análise: {analise}\n"
                f"Dor identificada: {dor}\n"
                f"Serviço Bloco relevante: {servico}\n\n"
                "Gere 3 ações concretas que a Bloco Produções pode propor."
            ),
        }],
    )
    linhas = [l.strip() for l in resp.content[0].text.strip().splitlines() if l.strip()]
    return linhas[:3] or ["- Criar vídeo institucional", "- Desenvolver calendário editorial", "- Produzir case de sucesso"]


# ─── Execução ─────────────────────────────────────────────────────────────────

def executar():
    from datetime import date

    print("\n[Etapa 4] Gerando apresentações HTML...")

    for arquivo in [ARQUIVO_PROSPECTS, ARQUIVO_ANALISES]:
        if not arquivo.exists():
            print(f"  ERRO: {arquivo} não encontrado. Execute as etapas anteriores.")
            return

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("  ERRO: ANTHROPIC_API_KEY não configurada no .env")
        return

    cliente = anthropic.Anthropic(api_key=api_key)
    prospects    = json.loads(ARQUIVO_PROSPECTS.read_text(encoding="utf-8"))
    analises_raw = json.loads(ARQUIVO_ANALISES.read_text(encoding="utf-8"))

    # suporta formato antigo (só "analise": string) e novo (dict com campos)
    analises: dict[str, dict] = {}
    for item in analises_raw:
        if isinstance(item.get("analise"), str) and len(item) <= 3:
            analises[item["empresa"]] = {"analise": item["analise"]}
        else:
            analises[item["empresa"]] = item

    PASTA_SAIDA.mkdir(exist_ok=True)
    hoje    = date.today().strftime("%d/%m/%Y")
    gerados = 0

    for empresa in prospects:
        nome           = empresa["nome"]
        analise_dados  = analises.get(nome, {})
        slug           = nome_para_arquivo(nome)
        arquivo_saida  = PASTA_SAIDA / f"{slug}.html"

        if arquivo_saida.exists():
            print(f"  {nome} — apresentação já existe, pulando.")
            continue

        print(f"  {nome} — gerando apresentação HTML...")
        try:
            plano = gerar_plano(cliente, nome, analise_dados)
        except Exception as e:
            print(f"    ERRO ao gerar plano: {e}")
            plano = ["Criar vídeo institucional", "Desenvolver calendário editorial", "Produzir case de sucesso"]

        html = _html(empresa, analise_dados, plano, hoje)
        arquivo_saida.write_text(html, encoding="utf-8")
        print(f"    Salvo: {arquivo_saida}")
        gerados += 1

    print(f"\n  Concluído: {gerados} apresentação(ões) gerada(s) em {PASTA_SAIDA}/")
    print("  Abra os arquivos .html no navegador · Ctrl+P para exportar como PDF")


if __name__ == "__main__":
    executar()
