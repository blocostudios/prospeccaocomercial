"""
Etapa 1 — Descoberta de empresas via fontes públicas gratuitas.

Fluxo:
  1. Busca empresas no DuckDuckGo por setor + cidades do Sul do Brasil
  2. Crawlea cada site encontrado para extrair CNPJ, e-mail e telefone
  3. Enriquece com a Brasil API (dados oficiais da Receita Federal)
  4. Salva resultado consolidado em dados/prospects.json

Não requer nenhuma chave de API.
"""

import json
import re
import time
from pathlib import Path
from urllib.parse import quote_plus, unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

ARQUIVO_SAIDA = Path("dados/prospects.json")

CIDADES = [
    "Porto Alegre", "Florianópolis", "Curitiba",
    "Blumenau", "Joinville", "Caxias do Sul",
    "Pelotas", "Londrina", "Maringá", "Ponta Grossa",
]

BUSCAS_POR_SETOR = {
    "publicidade": [
        "agência publicidade",
        "agência marketing digital",
        "agência comunicação",
    ],
    "advocacia": [
        "escritório advocacia",
        "advogados associados",
        "escritório jurídico",
    ],
    "medicina": [
        "clínica médica",
        "consultório médico",
        "centro médico",
    ],
}

MAX_RESULTADOS_POR_QUERY = 5
MAX_EMPRESAS_POR_SETOR = 8
TIMEOUT = 12
DELAY_ENTRE_BUSCAS = 2

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

RE_CNPJ = re.compile(r"\d{2}[\.\s]?\d{3}[\.\s]?\d{3}[\/\s]?\d{4}[-\s]?\d{2}")
RE_FONE = re.compile(r"\(?\d{2}\)?\s?\d{4,5}[-\s]?\d{4}")
RE_EMAIL = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

DOMINIOS_IGNORADOS = {
    "duckduckgo.com", "wikipedia.org", "youtube.com", "facebook.com",
    "instagram.com", "linkedin.com", "twitter.com", "google.com",
    "jusbrasil.com.br", "escavador.com", "migalhas.com.br",
}


# ─── DuckDuckGo ───────────────────────────────────────────────────────────────

def buscar_duckduckgo(query: str) -> list[dict]:
    """Busca no DuckDuckGo HTML sem API key. Retorna lista de {titulo, url}."""
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}&kl=br-pt"
    resultados = []

    try:
        resp = httpx.get(url, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
        soup = BeautifulSoup(resp.text, "html.parser")

        for item in soup.select(".result")[:MAX_RESULTADOS_POR_QUERY]:
            titulo_tag = item.select_one(".result__title a")
            if not titulo_tag:
                continue

            href = titulo_tag.get("href", "")
            if "uddg=" in href:
                match = re.search(r"uddg=([^&]+)", href)
                if match:
                    href = unquote(match.group(1))

            dominio = urlparse(href).netloc.replace("www.", "")
            if any(d in dominio for d in DOMINIOS_IGNORADOS) or not dominio:
                continue

            resultados.append({
                "titulo": titulo_tag.get_text(strip=True),
                "url": href,
            })
    except Exception as e:
        print(f"    [DDG] Erro: {e}")

    return resultados


# ─── Extração de contatos no site ─────────────────────────────────────────────

def extrair_contatos_do_html(html: str) -> dict:
    """Extrai CNPJ, e-mail e telefone do texto de uma página."""
    texto = BeautifulSoup(html, "html.parser").get_text(" ")

    cnpjs = RE_CNPJ.findall(texto)
    emails = [
        e for e in RE_EMAIL.findall(texto)
        if not e.endswith((".png", ".jpg", ".gif", ".svg", ".css", ".js"))
    ]
    fones = RE_FONE.findall(texto)

    return {
        "cnpj_raw": cnpjs[0] if cnpjs else "",
        "email": emails[0] if emails else "",
        "telefone": fones[0] if fones else "",
    }


def coletar_contatos_site(url: str) -> dict:
    """Tenta coletar contatos da home e de páginas secundárias."""
    if not url or not url.startswith("http"):
        return {}

    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    paginas = [url, urljoin(base, "/contato"), urljoin(base, "/contact"), urljoin(base, "/sobre")]
    contatos: dict = {}

    for pagina in paginas:
        try:
            resp = httpx.get(pagina, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
            if resp.status_code == 200:
                encontrados = extrair_contatos_do_html(resp.text)
                for campo in ["cnpj_raw", "email", "telefone"]:
                    if not contatos.get(campo) and encontrados.get(campo):
                        contatos[campo] = encontrados[campo]
        except Exception:
            pass

        if all(contatos.get(c) for c in ["cnpj_raw", "email", "telefone"]):
            break

    return contatos


# ─── Brasil API (Receita Federal) ─────────────────────────────────────────────

def limpar_cnpj(cnpj_raw: str) -> str:
    return re.sub(r"\D", "", cnpj_raw)


def consultar_brasil_api(cnpj_raw: str) -> dict:
    """
    Consulta Brasil API com CNPJ — gratuito, sem autenticação.
    Docs: https://brasilapi.com.br/docs#tag/CNPJ
    Retorna dados oficiais da Receita Federal.
    """
    cnpj = limpar_cnpj(cnpj_raw)
    if len(cnpj) != 14:
        return {}
    try:
        resp = httpx.get(
            f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}",
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {}


def extrair_dados_brasilapi(dados: dict) -> dict:
    if not dados:
        return {}
    nome = dados.get("nome_fantasia") or dados.get("razao_social", "")
    municipio = dados.get("municipio", "")
    uf = dados.get("uf", "")
    return {
        "nome_oficial": nome.title(),
        "razao_social": dados.get("razao_social", "").title(),
        "email_oficial": (dados.get("email") or "").lower(),
        "telefone_oficial": dados.get("ddd_telefone_1", ""),
        "municipio": f"{municipio}/{uf}" if municipio else "",
        "cnpj": dados.get("cnpj", ""),
        "situacao": dados.get("descricao_situacao_cadastral", ""),
        "setor_receita": dados.get("cnae_fiscal_descricao", ""),
    }


# ─── Montagem do prospect ─────────────────────────────────────────────────────

def montar_empresa(titulo: str, url: str, setor: str, contatos: dict, dados_rf: dict) -> dict:
    nome = dados_rf.get("nome_oficial") or titulo
    return {
        "nome": nome,
        "razao_social": dados_rf.get("razao_social", ""),
        "cnpj": dados_rf.get("cnpj") or limpar_cnpj(contatos.get("cnpj_raw", "")),
        "site": url,
        "email": dados_rf.get("email_oficial") or contatos.get("email", ""),
        "telefone": dados_rf.get("telefone_oficial") or contatos.get("telefone", ""),
        "municipio": dados_rf.get("municipio", ""),
        "setor": setor,
        "setor_receita": dados_rf.get("setor_receita", ""),
        "situacao_cadastral": dados_rf.get("situacao", ""),
        "aprovado": False,
    }


# ─── Execução principal ───────────────────────────────────────────────────────

def executar():
    print("\n[Etapa 1] Descobrindo empresas via fontes públicas brasileiras...")
    print("  Fontes: DuckDuckGo + sites das empresas + Brasil API (Receita Federal)\n")

    aprovacoes: dict[str, bool] = {}
    if ARQUIVO_SAIDA.exists():
        existentes = json.loads(ARQUIVO_SAIDA.read_text(encoding="utf-8"))
        aprovacoes = {e["nome"]: e.get("aprovado", False) for e in existentes}

    prospects: list[dict] = []
    urls_vistas: set[str] = set()

    for setor, termos in BUSCAS_POR_SETOR.items():
        print(f"  Setor: {setor.upper()}")
        encontradas = 0

        for termo in termos:
            if encontradas >= MAX_EMPRESAS_POR_SETOR:
                break

            for cidade in CIDADES[:4]:
                if encontradas >= MAX_EMPRESAS_POR_SETOR:
                    break

                query = f"{termo} {cidade}"
                print(f"    Buscando: \"{query}\"...")
                resultados = buscar_duckduckgo(query)
                time.sleep(DELAY_ENTRE_BUSCAS)

                for res in resultados:
                    dominio = urlparse(res["url"]).netloc
                    if dominio in urls_vistas or not dominio:
                        continue
                    urls_vistas.add(dominio)

                    print(f"      → {res['titulo'][:55]}")

                    contatos = coletar_contatos_site(res["url"])

                    dados_rf = {}
                    if contatos.get("cnpj_raw"):
                        raw = consultar_brasil_api(contatos["cnpj_raw"])
                        dados_rf = extrair_dados_brasilapi(raw)
                        if dados_rf:
                            situacao = dados_rf.get("situacao", "")
                            if situacao and "ATIVA" not in situacao.upper():
                                print(f"        Empresa inativa ({situacao}) — ignorando.")
                                continue
                            print(f"        CNPJ: {dados_rf.get('cnpj')} | {dados_rf.get('nome_oficial')}")

                    empresa = montar_empresa(res["titulo"], res["url"], setor, contatos, dados_rf)
                    empresa["aprovado"] = aprovacoes.get(empresa["nome"], False)
                    prospects.append(empresa)
                    encontradas += 1

        print(f"    {encontradas} empresa(s) encontrada(s).\n")

    ARQUIVO_SAIDA.parent.mkdir(exist_ok=True)
    ARQUIVO_SAIDA.write_text(
        json.dumps(prospects, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"  Total: {len(prospects)} empresa(s) salva(s) em {ARQUIVO_SAIDA}")
    print("\n  PRÓXIMO PASSO: Abra dados/prospects.json e marque")
    print('  "aprovado": true nas empresas que deseja prospectar.')


def buscar_com_parametros(params: dict, on_log=None, on_empresa=None) -> list:
    """
    Busca empresas com parâmetros customizados fornecidos pelo usuário.
    - params: dict com chaves opcionais: segmento, cidade, porte, cnae, keywords
    - on_log(msg): callback para mensagens de progresso
    - on_empresa(empresa): callback chamado para cada empresa encontrada
    """
    log = on_log or print

    # Parseia listas separadas por vírgula
    segmentos = [s.strip() for s in params.get("segmento", "").split(",") if s.strip()]
    cidades   = [c.strip() for c in params.get("cidade", "").split(",")   if c.strip()]
    keywords  = params.get("keywords", "").strip()
    cnae      = params.get("cnae", "").strip()

    # Defaults quando campos estão vazios
    if not segmentos:
        segmentos = ["empresa", "negócio", "prestadora de serviços"]
    if not cidades:
        cidades = CIDADES[:3]

    prospects: list[dict] = []
    urls_vistas: set[str] = set()

    for segmento in segmentos:
        for cidade in cidades[:4]:
            query = f"{segmento} {cidade}"
            if keywords:
                query += f" {keywords}"
            if cnae:
                query += f" CNAE {cnae}"

            log(f"Buscando: \"{query}\"...")
            resultados = buscar_duckduckgo(query)
            time.sleep(DELAY_ENTRE_BUSCAS)

            for res in resultados:
                dominio = urlparse(res["url"]).netloc
                if dominio in urls_vistas or not dominio:
                    continue
                urls_vistas.add(dominio)

                log(f"→ {res['titulo'][:60]}")

                contatos = coletar_contatos_site(res["url"])

                dados_rf = {}
                if contatos.get("cnpj_raw"):
                    raw = consultar_brasil_api(contatos["cnpj_raw"])
                    dados_rf = extrair_dados_brasilapi(raw)
                    if dados_rf:
                        situacao = dados_rf.get("situacao", "")
                        if situacao and "ATIVA" not in situacao.upper():
                            log(f"  Empresa inativa ({situacao}) — ignorando.")
                            continue
                        log(f"  CNPJ: {dados_rf.get('cnpj')} — {dados_rf.get('nome_oficial')}")

                empresa = montar_empresa(res["titulo"], res["url"], segmento, contatos, dados_rf)
                empresa["aprovado"] = False

                if on_empresa:
                    on_empresa(empresa)

                prospects.append(empresa)

    return prospects


if __name__ == "__main__":
    executar()
