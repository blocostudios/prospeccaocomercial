"""
Etapa 2 — Crawler leve de sites.

Para cada empresa em prospects.json:
  - Crawlea home + páginas secundárias (sobre, equipe, contato)
  - Extrai redes sociais (Instagram, LinkedIn, YouTube, TikTok, Facebook)
  - Extrai links de LinkedIn de pessoas e e-mails de contato
Salva conteúdo enriquecido em dados/sites_content.json.
"""

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

ARQUIVO_ENTRADA = Path("dados/prospects.json")
ARQUIVO_SAIDA   = Path("dados/sites_content.json")

PAGINAS_EXTRA = ["/sobre", "/sobre-nos", "/quem-somos", "/equipe", "/team",
                 "/contato", "/contact", "/servicos", "/services"]
TIMEOUT   = 10
MAX_CHARS = 4000

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BlocoProducoes-Bot/1.0)"}

# domínios de redes sociais a rastrear
REDES_MAP = {
    "instagram": "instagram.com",
    "linkedin_empresa": "linkedin.com/company",
    "linkedin_pessoa": "linkedin.com/in/",
    "youtube": "youtube.com",
    "tiktok": "tiktok.com",
    "facebook": "facebook.com",
    "twitter": "twitter.com",
    "x": "x.com",
}

RE_EMAIL = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def extrair_texto(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ").split())[:MAX_CHARS]


def extrair_redes_e_contatos(html: str) -> tuple[dict, str, str]:
    """
    Retorna (redes_dict, linkedin_contato, email_contato) a partir do HTML.
    """
    soup = BeautifulSoup(html, "html.parser")
    redes: dict[str, str] = {}
    linkedin_pessoa = ""
    email = ""

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href.startswith("http"):
            continue
        for nome, dominio in REDES_MAP.items():
            if dominio in href:
                if nome == "linkedin_pessoa":
                    if not linkedin_pessoa:
                        linkedin_pessoa = href
                elif nome == "linkedin_empresa":
                    if "linkedin_empresa" not in redes:
                        redes["linkedin"] = href
                elif nome not in redes:
                    redes[nome] = href

    # e-mails via mailto: ou regex no texto
    for a in soup.find_all("a", href=True):
        if a["href"].startswith("mailto:"):
            email = a["href"].replace("mailto:", "").split("?")[0].strip()
            break
    if not email:
        texto = soup.get_text(" ")
        matches = RE_EMAIL.findall(texto)
        matches = [m for m in matches
                   if not m.endswith((".png", ".jpg", ".gif", ".svg", ".js", ".css"))]
        if matches:
            email = matches[0]

    linkedin_contato = linkedin_pessoa or redes.get("linkedin", "")
    return redes, linkedin_contato, email


def coletar_site(nome: str, url: str) -> dict:
    if not url or not url.startswith("http"):
        return {"empresa": nome, "url": url, "conteudo": "",
                "redes_sociais": {}, "linkedin_contato": "", "email_crawled": ""}

    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    paginas = [url] + [urljoin(base, p) for p in PAGINAS_EXTRA]

    conteudo_total: list[str] = []
    redes_total: dict[str, str] = {}
    linkedin_contato = ""
    email_crawled = ""

    for pagina in paginas:
        try:
            resp = httpx.get(pagina, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
            if resp.status_code != 200:
                continue
            texto = extrair_texto(resp.text)
            if texto:
                conteudo_total.append(texto)
            redes, lk, em = extrair_redes_e_contatos(resp.text)
            redes_total.update({k: v for k, v in redes.items() if k not in redes_total})
            if not linkedin_contato and lk:
                linkedin_contato = lk
            if not email_crawled and em:
                email_crawled = em
        except Exception:
            pass

        if len(conteudo_total) >= 3 and redes_total and linkedin_contato:
            break

    conteudo = " | ".join(conteudo_total)[:MAX_CHARS * 2]
    return {
        "empresa": nome,
        "url": url,
        "conteudo": conteudo,
        "redes_sociais": redes_total,
        "linkedin_contato": linkedin_contato,
        "email_crawled": email_crawled,
    }


def executar():
    print("\n[Etapa 2] Crawleando sites das empresas...")

    if not ARQUIVO_ENTRADA.exists():
        print("  ERRO: dados/prospects.json não encontrado. Execute a Etapa 1 primeiro.")
        return

    empresas = json.loads(ARQUIVO_ENTRADA.read_text(encoding="utf-8"))

    # preserva resultados já coletados para não repetir
    existentes: dict[str, dict] = {}
    if ARQUIVO_SAIDA.exists():
        for item in json.loads(ARQUIVO_SAIDA.read_text(encoding="utf-8")):
            existentes[item["empresa"]] = item

    resultados = []
    for i, empresa in enumerate(empresas, 1):
        nome = empresa.get("nome", "Desconhecida")
        url  = empresa.get("site", "")

        if nome in existentes and existentes[nome].get("conteudo"):
            print(f"  [{i}/{len(empresas)}] {nome} — já coletado, pulando.")
            resultados.append(existentes[nome])
            continue

        print(f"  [{i}/{len(empresas)}] {nome} — {url or 'sem site'}")
        resultado = coletar_site(nome, url)

        redes_str = ", ".join(f"{k}: {v}" for k, v in resultado["redes_sociais"].items())
        if redes_str:
            print(f"    Redes: {redes_str[:80]}")
        if resultado["linkedin_contato"]:
            print(f"    LinkedIn: {resultado['linkedin_contato'][:60]}")

        resultados.append(resultado)

    ARQUIVO_SAIDA.parent.mkdir(exist_ok=True)
    ARQUIVO_SAIDA.write_text(
        json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    com_conteudo = sum(1 for r in resultados if r["conteudo"])
    com_redes    = sum(1 for r in resultados if r.get("redes_sociais"))
    print(f"\n  Concluído: {com_conteudo}/{len(resultados)} sites com conteúdo | "
          f"{com_redes}/{len(resultados)} com redes sociais.")
    print(f"  Salvo em {ARQUIVO_SAIDA}")


if __name__ == "__main__":
    executar()
