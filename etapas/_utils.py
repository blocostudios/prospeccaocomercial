"""Utilitários compartilhados entre as etapas."""

import re


def nome_para_arquivo(nome: str) -> str:
    """Converte nome da empresa em slug seguro para nome de arquivo."""
    slug = re.sub(r"[^\w\s-]", "", nome.lower())
    slug = re.sub(r"[\s_-]+", "_", slug).strip("_")
    return slug
