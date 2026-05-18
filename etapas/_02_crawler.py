"""
Etapa 2 — Crawler leve de sites.

Para cada empresa em prospects.json, faz GET na home e tenta
buscar /sobre e /servicos. Erros são ignorados silenciosamente.
Salva conteúdo em dados/sites_content.json.
"""

import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

ARQUIVO_ENTRADA = Path("dados/prospects.json")
ARQUIVO_SAIDA = Path("dados/sites_content.json")

PAGINAS_EXTRA = ["/sobre", "/sobre-nos", "/quem-somos", "/servicos", "/services"]
TIMEOUT = 10
MAX_CHARS = 3000  # limita o texto para não sobrecarregar a API


def extrair_texto(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    # Remove scripts e estilos
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ").split())[:MAX_CHARS]


def coletar_site(nome: str, url: str) -> dict:
    """Tenta coletar texto da home e de páginas secundárias."""
    if not url or not url.startswith("http"):
        return {"empresa": nome, "url": url, "conteudo": ""}

    conteudo_total = []

    # Garante URL base limpa
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    paginas = [url] + [urljoin(base, p) for p in PAGINAS_EXTRA]

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; BlocoProducoes-Bot/1.0)"
        )
    }

    for pagina in paginas:
        try:
            resp = httpx.get(pagina, headers=headers, timeout=TIMEOUT, follow_redirects=True)
            if resp.status_code == 200:
                texto = extrair_texto(resp.text)
                if texto:
                    conteudo_total.append(texto)
        except Exception:
            pass  # ignora silenciosamente timeouts, DNS, SSL, etc.

    conteudo = " | ".join(conteudo_total)[:MAX_CHARS * 2]
    return {"empresa": nome, "url": url, "conteudo": conteudo}


def executar():
    print("\n[Etapa 2] Crawleando sites das empresas...")

    if not ARQUIVO_ENTRADA.exists():
        print("  ERRO: dados/prospects.json não encontrado. Execute a Etapa 1 primeiro.")
        return

    empresas = json.loads(ARQUIVO_ENTRADA.read_text(encoding="utf-8"))
    resultados = []

    for i, empresa in enumerate(empresas, 1):
        nome = empresa.get("nome", "Desconhecida")
        url = empresa.get("site", "")
        print(f"  [{i}/{len(empresas)}] {nome} — {url or 'sem site'}")
        resultado = coletar_site(nome, url)
        resultados.append(resultado)

    ARQUIVO_SAIDA.parent.mkdir(exist_ok=True)
    ARQUIVO_SAIDA.write_text(
        json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    com_conteudo = sum(1 for r in resultados if r["conteudo"])
    print(f"\n  Concluído: {com_conteudo}/{len(resultados)} site(s) com conteúdo capturado.")
    print(f"  Salvo em {ARQUIVO_SAIDA}")


if __name__ == "__main__":
    executar()
