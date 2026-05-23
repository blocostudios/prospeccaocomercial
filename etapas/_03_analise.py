"""
Etapa 3 — Análise estruturada via Anthropic API.

Para cada empresa em sites_content.json, gera um JSON com:
  prioridade, por_que_oportunidade, dor_provavel, servico_bloco,
  pessoa_chave, cargo, linkedin_contato, abordagem_sugerida, analise

Salva resultado em dados/analyses.json.
Usa prompt caching para economizar tokens nas chamadas repetidas.
"""

import json
import os
import re
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

ARQUIVO_CONTEUDO = Path("dados/sites_content.json")
ARQUIVO_SAIDA    = Path("dados/analyses.json")

BLOCO_BIO = os.getenv(
    "BLOCO_BIO",
    "A Bloco Produções é um estúdio criativo e estratégico especializado em produção "
    "audiovisual: vídeos institucionais, reels, cases de sucesso, calendários editoriais "
    "e conteúdo para redes sociais. Atende marcas que precisam escalar presença digital "
    "com produção recorrente e consistente.",
)

SYSTEM_PROMPT = f"""Você é um especialista em marketing audiovisual da Bloco Produções.

Sobre a Bloco Produções:
{BLOCO_BIO}

Analise o conteúdo do site desta empresa e retorne SOMENTE um JSON válido — sem markdown, sem texto extra, sem blocos de código. O JSON deve ter exatamente estas chaves:

{{
  "prioridade": "Alta|Média|Baixa",
  "por_que_oportunidade": "Por que esta empresa é uma boa oportunidade para a Bloco (2-3 frases com dados e contexto concreto)",
  "dor_provavel": "Principal dor ou lacuna de comunicação audiovisual desta empresa (1-2 frases diretas)",
  "servico_bloco": "Serviço(s) da Bloco mais relevantes para esta empresa (ex: produção audiovisual recorrente + calendário editorial multi-marca)",
  "pessoa_chave": "Nome completo da pessoa de decisão identificada no site (CEO, Diretor, Fundador). Deixe vazio se não encontrado.",
  "cargo": "Cargo desta pessoa (ex: CEO, Diretor de Marketing, Co-fundador)",
  "linkedin_contato": "URL do LinkedIn da empresa ou pessoa encontrada no site, ou e-mail se disponível",
  "abordagem_sugerida": "Assunto do e-mail sugerido + estratégia de abordagem personalizada e específica (2-3 frases)",
  "analise": "Diagnóstico completo: uso atual de audiovisual, oportunidades identificadas e como a Bloco pode contribuir (2-3 parágrafos)"
}}

Critérios de prioridade:
- Alta: presença digital limitada para o porte/setor, crescimento/captação recente identificada, ou múltiplas marcas/produtos sem calendário editorial estruturado
- Média: presença razoável mas com lacunas claras de produção audiovisual
- Baixa: produção audiovisual já bem desenvolvida ou oportunidade pouco clara"""

TEXTO_SEM_CONTEUDO = (
    "Site não acessível. Analise com base no setor e nome da empresa."
)

RE_JSON = re.compile(r"\{[\s\S]*\}", re.MULTILINE)


def analisar_empresa(cliente: anthropic.Anthropic, nome: str, item: dict) -> dict:
    conteudo = item.get("conteudo", "").strip() or TEXTO_SEM_CONTEUDO
    redes = item.get("redes_sociais", {})
    linkedin_crawled = item.get("linkedin_contato", "")
    email_crawled = item.get("email_crawled", "")

    contexto_extra = ""
    if redes:
        redes_str = " | ".join(f"{k}: {v}" for k, v in redes.items())
        contexto_extra += f"\nRedes sociais encontradas: {redes_str}"
    if linkedin_crawled:
        contexto_extra += f"\nLinkedIn encontrado: {linkedin_crawled}"
    if email_crawled:
        contexto_extra += f"\nE-mail encontrado: {email_crawled}"

    mensagem = cliente.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1400,
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": (
                f"Empresa: {nome}\n"
                f"URL: {item.get('url', '')}"
                f"{contexto_extra}\n\n"
                f"Conteúdo do site:\n{conteudo}"
            ),
        }],
    )

    raw = mensagem.content[0].text.strip()

    # tenta extrair JSON mesmo que venha com texto extra
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = RE_JSON.search(raw)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

    # fallback: retorna só o texto como "analise"
    return {"analise": raw, "prioridade": "Média"}


def executar():
    print("\n[Etapa 3] Analisando empresas com IA (saída estruturada)...")

    if not ARQUIVO_CONTEUDO.exists():
        print("  ERRO: dados/sites_content.json não encontrado. Execute a Etapa 2 primeiro.")
        return

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("  ERRO: ANTHROPIC_API_KEY não configurada no .env")
        return

    cliente = anthropic.Anthropic(api_key=api_key)
    conteudos = json.loads(ARQUIVO_CONTEUDO.read_text(encoding="utf-8"))

    # carrega análises existentes (suporta formato antigo string e novo dict)
    existentes: dict[str, dict] = {}
    if ARQUIVO_SAIDA.exists():
        for item in json.loads(ARQUIVO_SAIDA.read_text(encoding="utf-8")):
            val = item.get("analise_estruturada") or item
            # normaliza formato antigo
            if isinstance(item.get("analise"), str) and "prioridade" not in item:
                existentes[item["empresa"]] = {"analise": item["analise"], "prioridade": "Média"}
            else:
                existentes[item["empresa"]] = item

    resultados = []
    for i, item in enumerate(conteudos, 1):
        nome = item["empresa"]

        if nome in existentes and existentes[nome].get("analise"):
            print(f"  [{i}/{len(conteudos)}] {nome} — análise já existente, pulando.")
            entry = existentes[nome].copy()
            entry["empresa"] = nome
            resultados.append(entry)
            continue

        print(f"  [{i}/{len(conteudos)}] {nome} — analisando...")
        try:
            dados = analisar_empresa(cliente, nome, item)
            dados["empresa"] = nome
            prioridade = dados.get("prioridade", "?")
            pessoa = dados.get("pessoa_chave", "")
            print(f"    Prioridade: {prioridade}" + (f" | Pessoa-chave: {pessoa}" if pessoa else ""))
            resultados.append(dados)
        except Exception as e:
            print(f"    ERRO: {e}")
            resultados.append({"empresa": nome, "analise": "", "prioridade": "Média"})

    ARQUIVO_SAIDA.parent.mkdir(exist_ok=True)
    ARQUIVO_SAIDA.write_text(
        json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    alta  = sum(1 for r in resultados if r.get("prioridade") == "Alta")
    media = sum(1 for r in resultados if r.get("prioridade") == "Média")
    baixa = sum(1 for r in resultados if r.get("prioridade") == "Baixa")
    print(f"\n  Concluído: {len(resultados)} empresa(s) — Alta: {alta} | Média: {media} | Baixa: {baixa}")
    print(f"  Salvo em {ARQUIVO_SAIDA}")


if __name__ == "__main__":
    executar()
