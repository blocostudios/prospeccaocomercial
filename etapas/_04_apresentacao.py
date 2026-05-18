"""
Etapa 4 — Geração de apresentações personalizadas em Markdown.

Combina análise da IA com a bio da Bloco Produções e gera
um arquivo .md por empresa em /apresentacoes/.
"""

import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from etapas._utils import nome_para_arquivo

load_dotenv()

ARQUIVO_PROSPECTS = Path("dados/prospects.json")
ARQUIVO_ANALISES = Path("dados/analyses.json")
PASTA_SAIDA = Path("apresentacoes")

BLOCO_BIO = os.getenv(
    "BLOCO_BIO",
    "A Bloco Produções é uma produtora audiovisual especializada em vídeos institucionais, "
    "reels, cases de sucesso e conteúdo para redes sociais.",
)

TEMPLATE = """# Apresentação — {nome_empresa}

**Destinatário:** {ponto_focal}
**Data:** {data}

---

## Sobre a {nome_empresa}

{analise}

---

## Quem somos — Bloco Produções

{bloco_bio}

---

## Plano de ação sugerido

{plano_de_acao}

---

*Apresentação gerada pela Bloco Produções. Para mais informações, entre em contato.*
"""


def gerar_plano(cliente: anthropic.Anthropic, nome: str, analise: str) -> str:
    """Pede à IA 3 bullet points de plano de ação para a empresa."""
    resp = cliente.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Com base nesta análise sobre a empresa {nome}:\n\n{analise}\n\n"
                    "Gere exatamente 3 bullet points de plano de ação concreto que a "
                    "Bloco Produções pode propor. Formato: cada linha começa com '- '. "
                    "Seja específico e prático."
                ),
            }
        ],
    )
    return resp.content[0].text.strip()



def executar():
    from datetime import date

    print("\n[Etapa 4] Gerando apresentações...")

    for arquivo in [ARQUIVO_PROSPECTS, ARQUIVO_ANALISES]:
        if not arquivo.exists():
            print(f"  ERRO: {arquivo} não encontrado. Execute as etapas anteriores.")
            return

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("  ERRO: ANTHROPIC_API_KEY não configurada no .env")
        return

    cliente = anthropic.Anthropic(api_key=api_key)
    prospects = json.loads(ARQUIVO_PROSPECTS.read_text(encoding="utf-8"))
    analises_lista = json.loads(ARQUIVO_ANALISES.read_text(encoding="utf-8"))
    analises = {item["empresa"]: item["analise"] for item in analises_lista}

    PASTA_SAIDA.mkdir(exist_ok=True)
    hoje = date.today().strftime("%d/%m/%Y")
    gerados = 0

    for empresa in prospects:
        nome = empresa["nome"]
        analise = analises.get(nome, "Análise não disponível.")
        ponto_focal = empresa.get("ponto_focal", "Prezado(a) responsável")
        arquivo_saida = PASTA_SAIDA / f"{nome_para_arquivo(nome)}.md"

        # Não regera se já existir
        if arquivo_saida.exists():
            print(f"  {nome} — apresentação já existe, pulando.")
            continue

        print(f"  {nome} — gerando plano de ação...")
        try:
            plano = gerar_plano(cliente, nome, analise)
        except Exception as e:
            print(f"    ERRO ao gerar plano: {e}")
            plano = "- Criar vídeo institucional\n- Desenvolver conteúdo para redes sociais\n- Produzir case de sucesso"

        conteudo = TEMPLATE.format(
            nome_empresa=nome,
            ponto_focal=ponto_focal,
            data=hoje,
            analise=analise,
            bloco_bio=BLOCO_BIO,
            plano_de_acao=plano,
        )

        arquivo_saida.write_text(conteudo, encoding="utf-8")
        print(f"    Salvo em {arquivo_saida}")
        gerados += 1

    print(f"\n  Concluído: {gerados} apresentação(ões) nova(s) gerada(s) em {PASTA_SAIDA}/")


if __name__ == "__main__":
    executar()
