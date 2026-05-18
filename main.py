"""
main.py — Sistema de Prospecção Outbound — Bloco Produções

Menu interativo para executar cada etapa do fluxo.
"""

import sys
from pathlib import Path

# Garante que imports relativos funcionem independente de onde o script é chamado
sys.path.insert(0, str(Path(__file__).parent))


MENU = """
╔══════════════════════════════════════════════════╗
║   BLOCO PRODUÇÕES — Sistema de Prospecção        ║
╠══════════════════════════════════════════════════╣
║  1) Buscar empresas-alvo         (Etapa 1)       ║
║  2) Crawlear sites               (Etapa 2)       ║
║  3) Analisar com IA              (Etapa 3)       ║
║  4) Gerar apresentações          (Etapa 4)       ║
║  5) Enviar e-mails aprovados     (Etapa 5)       ║
║  6) Ver auditoria                (Etapa 6)       ║
║  0) Sair                                         ║
╚══════════════════════════════════════════════════╝
"""


def checar_env():
    """Avisa se o .env não existe ainda."""
    if not Path(".env").exists():
        print("\n  AVISO: arquivo .env não encontrado.")
        print("  Copie .env.example para .env e preencha as variáveis antes de continuar.\n")


def executar_etapa(opcao: str):
    if opcao == "1":
        from etapas import _01_busca as mod
        mod.executar()
    elif opcao == "2":
        from etapas import _02_crawler as mod
        mod.executar()
    elif opcao == "3":
        from etapas import _03_analise as mod
        mod.executar()
    elif opcao == "4":
        from etapas import _04_apresentacao as mod
        mod.executar()
    elif opcao == "5":
        from etapas import _05_email as mod
        mod.executar()
    elif opcao == "6":
        from etapas import _06_auditoria as mod
        mod.executar()


def main():
    checar_env()
    while True:
        print(MENU)
        opcao = input("  Escolha uma opção: ").strip()

        if opcao == "0":
            print("\n  Até logo!\n")
            break
        elif opcao in {"1", "2", "3", "4", "5", "6"}:
            try:
                executar_etapa(opcao)
            except KeyboardInterrupt:
                print("\n  Interrompido pelo usuário.")
            except Exception as e:
                print(f"\n  ERRO inesperado: {e}")
        else:
            print("  Opção inválida. Tente novamente.")


if __name__ == "__main__":
    main()
