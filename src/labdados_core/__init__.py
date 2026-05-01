"""
labdados-core — núcleo compartilhado entre o backend do escritório de apoio
do LabDados e o SDK Python ``labdados``.

Re-export apenas o módulo ``viabilidade`` para evitar imports custosos
(juscraper) quando o consumidor só precisa de uma parte do núcleo.
"""

from labdados_core._version import __version__

__all__ = ["__version__"]
