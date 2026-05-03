"""Exceções específicas do pipeline de anonimização."""

from __future__ import annotations


class ModeloIndisponivel(RuntimeError):
    """Lançada quando ``transformers``/``torch`` não estão instalados.

    O caller deve instalar o extra apropriado:
    ``labdados-core[anonimizacao-cpu]`` ou
    ``labdados-core[anonimizacao-gpu]``.
    """
