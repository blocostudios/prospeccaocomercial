"""
Etapa 3 — Análise de IA via Anthropic API.

Para cada empresa com conteúdo em sites_content.json, chama
claude-sonnet-4-20250514 para identificar oportunidades audiovisuais.
Salva resultado em dados/analyses.json.
"""

import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

ARQUIVO_CONTEUDO = Path("dados/sites_content.json")
ARQUIVO_SAIDA = Path("dados/analyses.json")

SYSTEM_PROMPT = (
    "Você é um especialista em marketing audiovisual. Analise o site desta empresa e "
    "identifique: (1) como ela atualmente usa ou não usa produção audiovisual em sua "
    "comunicação, (2) quais oportunidades existem para melhorar sua presença com vídeo "
    "institucional, reel, case, conteúdo para redes sociais ou eventos, (3) um insight "
    "personalizado de como a Bloco Produções poderia contribuir. Seja direto e prático. "
    "Máximo 3 parágrafos."
)

TEXTO_SEM_CONTEUDO = (
    "Não foi possível acessar o site desta empresa. Com base apenas no setor de atuação, "
    "há oportunidades claras para vídeo institucional e conteúdo para redes sociais."
)


def analisar_empresa(cliente: anthropic.Anthropic, nome: str, conteudo: str) -> str:
    """Chama a API e retorna a análise como string."""
    texto = conteudo.strip() if conteudo.strip() else TEXTO_SEM_CONTEUDO

    mensagem = cliente.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Empresa: {nome}\n\n"
                    f"Conteúdo extraído do site:\n{texto}"
                ),
            }
        ],
    )
    return mensagem.content[0].text


def executar():
    print("\n[Etapa 3] Analisando empresas com IA...")

    if not ARQUIVO_CONTEUDO.exists():
        print("  ERRO: dados/sites_content.json não encontrado. Execute a Etapa 2 primeiro.")
        return

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("  ERRO: ANTHROPIC_API_KEY não configurada no .env")
        return

    cliente = anthropic.Anthropic(api_key=api_key)
    conteudos = json.loads(ARQUIVO_CONTEUDO.read_text(encoding="utf-8"))

    # Carrega análises já existentes para não repetir chamadas
    existentes: dict[str, str] = {}
    if ARQUIVO_SAIDA.exists():
        for item in json.loads(ARQUIVO_SAIDA.read_text(encoding="utf-8")):
            existentes[item["empresa"]] = item["analise"]

    resultados = []
    for i, item in enumerate(conteudos, 1):
        nome = item["empresa"]

        if nome in existentes:
            print(f"  [{i}/{len(conteudos)}] {nome} — análise já existente, pulando.")
            resultados.append({"empresa": nome, "analise": existentes[nome]})
            continue

        print(f"  [{i}/{len(conteudos)}] {nome} — analisando...")
        try:
            analise = analisar_empresa(cliente, nome, item.get("conteudo", ""))
            resultados.append({"empresa": nome, "analise": analise})
            print(f"    OK")
        except Exception as e:
            print(f"    ERRO: {e}")
            resultados.append({"empresa": nome, "analise": ""})

    ARQUIVO_SAIDA.parent.mkdir(exist_ok=True)
    ARQUIVO_SAIDA.write_text(
        json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    com_analise = sum(1 for r in resultados if r["analise"])
    print(f"\n  Concluído: {com_analise}/{len(resultados)} empresa(s) analisada(s).")
    print(f"  Salvo em {ARQUIVO_SAIDA}")


if __name__ == "__main__":
    executar()
