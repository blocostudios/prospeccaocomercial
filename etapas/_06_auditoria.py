"""
Etapa 6 — Visualização do log de auditoria.

Lê audit_log.json e exibe um resumo formatado no terminal.
"""

import json
from pathlib import Path

ARQUIVO_AUDITORIA = Path("dados/audit_log.json")


def executar():
    print("\n[Etapa 6] Auditoria de atividades\n")

    if not ARQUIVO_AUDITORIA.exists():
        print("  Nenhum registro de auditoria encontrado ainda.")
        return

    log = json.loads(ARQUIVO_AUDITORIA.read_text(encoding="utf-8"))

    if not log:
        print("  Log de auditoria está vazio.")
        return

    # Agrupa por status
    por_status: dict[str, list] = {}
    for entrada in log:
        status = entrada.get("status", "desconhecido")
        por_status.setdefault(status, []).append(entrada)

    print(f"  Total de registros: {len(log)}\n")
    print(f"  {'STATUS':<12} {'EMPRESA':<35} {'E-MAIL':<35} {'DATA/HORA'}")
    print("  " + "-" * 100)

    for entrada in sorted(log, key=lambda x: x.get("timestamp", "")):
        status = entrada.get("status", "?")
        empresa = entrada.get("empresa", "?")[:33]
        email = entrada.get("email", "?")[:33]
        timestamp = entrada.get("timestamp", "?")[:19].replace("T", " ")
        erro = entrada.get("erro", "")

        linha = f"  {status:<12} {empresa:<35} {email:<35} {timestamp}"
        print(linha)
        if erro:
            print(f"  {'':12} Erro: {erro}")

    print("\n  Resumo por status:")
    for status, entradas in sorted(por_status.items()):
        print(f"    {status}: {len(entradas)}")


if __name__ == "__main__":
    executar()
