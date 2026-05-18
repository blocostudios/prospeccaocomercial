"""
Etapa 5 — Envio de e-mails via Gmail API (OAuth2).

Só envia para empresas com "aprovado": true em prospects.json.
Registra cada envio no audit_log.json via 06_auditoria.py.

Setup inicial (uma única vez):
1. Acesse https://console.cloud.google.com/
2. Crie um projeto > APIs & Services > Enable "Gmail API"
3. Credentials > Create > OAuth 2.0 Client ID (tipo: Desktop app)
4. Baixe o JSON e salve como credentials/gmail_credentials.json
5. Na primeira execução, um navegador abrirá para autorização.
   O token ficará salvo em credentials/gmail_token.json.
"""

import base64
import json
import mimetypes
import os
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

ARQUIVO_PROSPECTS = Path("dados/prospects.json")
PASTA_APRESENTACOES = Path("apresentacoes")
ARQUIVO_AUDITORIA = Path("dados/audit_log.json")
CREDENTIALS_DIR = Path("credentials")
CREDENTIALS_FILE = CREDENTIALS_DIR / "gmail_credentials.json"
TOKEN_FILE = CREDENTIALS_DIR / "gmail_token.json"

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
REMETENTE = os.getenv("GMAIL_REMETENTE", "")

ASSUNTO_TEMPLATE = "Uma ideia para {nome_empresa} — Bloco Produções"

CORPO_TEMPLATE = """\
Olá, {ponto_focal}!

Meu nome é [SEU NOME] e faço parte da equipe da Bloco Produções, produtora audiovisual \
do Sul do Brasil.

Estudei um pouco sobre a {nome_empresa} e acredito que temos algumas ideias interessantes \
de como a comunicação audiovisual pode amplificar a presença de vocês — \
seja com vídeo institucional, reels, cases ou conteúdo para redes sociais.

Preparei uma apresentação personalizada que está em anexo. \
Seria um prazer conversar rapidamente sobre isso.

Fico à disposição!

Atenciosamente,
[SEU NOME]
Bloco Produções
[SEU TELEFONE]
"""


def autenticar_gmail():
    """Realiza autenticação OAuth2. Abre navegador na primeira vez."""
    CREDENTIALS_DIR.mkdir(exist_ok=True)
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"Arquivo de credenciais não encontrado: {CREDENTIALS_FILE}\n"
                    "Siga as instruções no cabeçalho deste arquivo para configurar o Gmail OAuth2."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds)


def construir_email(destinatario: str, assunto: str, corpo: str, anexo: Path) -> dict:
    """Monta a mensagem MIME com anexo .md."""
    msg = MIMEMultipart()
    msg["to"] = destinatario
    msg["from"] = REMETENTE
    msg["subject"] = assunto
    msg.attach(MIMEText(corpo, "plain", "utf-8"))

    if anexo.exists():
        mime_type, _ = mimetypes.guess_type(str(anexo))
        mime_type = mime_type or "application/octet-stream"
        with open(anexo, "rb") as f:
            parte = MIMEApplication(f.read(), Name=anexo.name)
        parte["Content-Disposition"] = f'attachment; filename="{anexo.name}"'
        msg.attach(parte)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw}


def registrar_auditoria(entrada: dict):
    """Adiciona uma entrada no audit_log.json."""
    log = []
    if ARQUIVO_AUDITORIA.exists():
        log = json.loads(ARQUIVO_AUDITORIA.read_text(encoding="utf-8"))
    log.append(entrada)
    ARQUIVO_AUDITORIA.parent.mkdir(exist_ok=True)
    ARQUIVO_AUDITORIA.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def executar():
    from datetime import datetime

    print("\n[Etapa 5] Enviando e-mails para empresas aprovadas...")

    if not ARQUIVO_PROSPECTS.exists():
        print("  ERRO: dados/prospects.json não encontrado.")
        return

    if not REMETENTE:
        print("  ERRO: GMAIL_REMETENTE não configurado no .env")
        return

    prospects = json.loads(ARQUIVO_PROSPECTS.read_text(encoding="utf-8"))
    aprovadas = [e for e in prospects if e.get("aprovado") is True]

    if not aprovadas:
        print('  Nenhuma empresa com "aprovado": true encontrada.')
        print('  Edite dados/prospects.json e marque as empresas desejadas.')
        return

    print(f"  {len(aprovadas)} empresa(s) aprovada(s) para envio.")

    try:
        servico = autenticar_gmail()
    except FileNotFoundError as e:
        print(f"  ERRO de autenticação: {e}")
        return

    enviados = 0
    for empresa in aprovadas:
        nome = empresa["nome"]
        email_dest = empresa.get("email", "")
        ponto_focal = empresa.get("ponto_focal", "Prezado(a) responsável")

        if not email_dest:
            print(f"  {nome} — sem e-mail cadastrado, pulando.")
            continue

        # Verifica se já foi enviado
        if ARQUIVO_AUDITORIA.exists():
            log = json.loads(ARQUIVO_AUDITORIA.read_text(encoding="utf-8"))
            ja_enviado = any(
                e["empresa"] == nome and e["status"] == "enviado" for e in log
            )
            if ja_enviado:
                print(f"  {nome} — e-mail já enviado anteriormente, pulando.")
                continue

        from etapas._utils import nome_para_arquivo
        slug = nome_para_arquivo(nome)
        anexo = PASTA_APRESENTACOES / f"{slug}.md"

        assunto = ASSUNTO_TEMPLATE.format(nome_empresa=nome)
        corpo = CORPO_TEMPLATE.format(nome_empresa=nome, ponto_focal=ponto_focal)

        print(f"  Enviando para {nome} <{email_dest}>...")
        entrada_log = {
            "empresa": nome,
            "email": email_dest,
            "timestamp": datetime.now().isoformat(),
            "status": "pendente",
        }

        try:
            mensagem = construir_email(email_dest, assunto, corpo, anexo)
            servico.users().messages().send(userId="me", body=mensagem).execute()
            entrada_log["status"] = "enviado"
            print(f"    OK — enviado.")
            enviados += 1
        except Exception as e:
            entrada_log["status"] = "erro"
            entrada_log["erro"] = str(e)
            print(f"    ERRO: {e}")

        registrar_auditoria(entrada_log)

    print(f"\n  Concluído: {enviados}/{len(aprovadas)} e-mail(s) enviado(s).")


if __name__ == "__main__":
    executar()
