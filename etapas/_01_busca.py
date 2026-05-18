"""
Etapa 1 — Busca de empresas-alvo.

Tenta usar a API da Explorium. Se a chave não estiver configurada,
gera um conjunto de empresas mock para que o restante do fluxo funcione.
Salva resultado em dados/prospects.json.
"""

import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

EXPLORIUM_API_KEY = os.getenv("EXPLORIUM_API_KEY", "")
ARQUIVO_SAIDA = Path("dados/prospects.json")

SETORES = ["publicidade", "advocacia", "medicina"]
REGIAO = "Sul do Brasil"


def buscar_via_explorium() -> list[dict]:
    """Chama a API REST da Explorium para buscar empresas."""
    url = "https://api.explorium.ai/v1/businesses/discover"
    headers = {
        "Authorization": f"Bearer {EXPLORIUM_API_KEY}",
        "Content-Type": "application/json",
    }
    empresas = []

    for setor in SETORES:
        payload = {
            "filters": {
                "country": "Brazil",
                "region": REGIAO,
                "industry": setor,
            },
            "limit": 10,
        }
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=15)
            resp.raise_for_status()
            dados = resp.json()
            for item in dados.get("results", []):
                empresas.append({
                    "nome": item.get("company_name", ""),
                    "site": item.get("website", ""),
                    "email": item.get("email", ""),
                    "telefone": item.get("phone", ""),
                    "setor": setor,
                    "aprovado": False,
                })
        except Exception as e:
            print(f"  [Explorium] Erro no setor '{setor}': {e}")

    return empresas


def gerar_mock() -> list[dict]:
    """Retorna empresas de exemplo para testes sem chave de API."""
    print("  [Mock] Usando dados de demonstração (EXPLORIUM_API_KEY não configurado).")
    return [
        {
            "nome": "Agência Criativa Sul",
            "site": "https://example.com/agenciacriativasul",
            "email": "contato@agenciacriativasul.com.br",
            "telefone": "(51) 3000-0001",
            "setor": "publicidade",
            "aprovado": False,
        },
        {
            "nome": "Studio Mídia & Branding",
            "site": "https://example.com/studiomidia",
            "email": "ola@studiomidia.com.br",
            "telefone": "(41) 3000-0002",
            "setor": "publicidade",
            "aprovado": False,
        },
        {
            "nome": "Advocacia Fontana & Associados",
            "site": "https://example.com/fontanaadvocacia",
            "email": "adm@fontanaadvocacia.com.br",
            "telefone": "(51) 3000-0003",
            "setor": "advocacia",
            "aprovado": False,
        },
        {
            "nome": "Escritório Jurídico Meridional",
            "site": "https://example.com/juridicomeridional",
            "email": "contato@juridicomeridional.com.br",
            "telefone": "(48) 3000-0004",
            "setor": "advocacia",
            "aprovado": False,
        },
        {
            "nome": "Clínica Saúde Plena",
            "site": "https://example.com/saudeplena",
            "email": "recepcao@saudeplena.com.br",
            "telefone": "(41) 3000-0005",
            "setor": "medicina",
            "aprovado": False,
        },
        {
            "nome": "Centro Médico Vitalis",
            "site": "https://example.com/vitalis",
            "email": "contato@vitalis.com.br",
            "telefone": "(51) 3000-0006",
            "setor": "medicina",
            "aprovado": False,
        },
    ]


def executar():
    print("\n[Etapa 1] Buscando empresas-alvo...")

    if EXPLORIUM_API_KEY:
        print(f"  Consultando Explorium para setores: {', '.join(SETORES)}")
        empresas = buscar_via_explorium()
        if not empresas:
            print("  Explorium não retornou resultados. Usando mock como fallback.")
            empresas = gerar_mock()
    else:
        empresas = gerar_mock()

    # Preserva aprovações manuais se o arquivo já existir
    if ARQUIVO_SAIDA.exists():
        existentes = json.loads(ARQUIVO_SAIDA.read_text(encoding="utf-8"))
        aprovacoes = {e["nome"]: e.get("aprovado", False) for e in existentes}
        for e in empresas:
            if e["nome"] in aprovacoes:
                e["aprovado"] = aprovacoes[e["nome"]]

    ARQUIVO_SAIDA.parent.mkdir(exist_ok=True)
    ARQUIVO_SAIDA.write_text(
        json.dumps(empresas, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"  {len(empresas)} empresa(s) salva(s) em {ARQUIVO_SAIDA}")
    print("\n  PRÓXIMO PASSO: Abra dados/prospects.json e marque")
    print('  "aprovado": true nas empresas que deseja prospectar.')


if __name__ == "__main__":
    executar()
