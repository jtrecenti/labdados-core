"""
Análise de viabilidade — superfície pública.

>>> from labdados_core.viabilidade import analyze_form, render_report

Estes são os pontos de entrada estáveis. Tudo mais (módulos privados de
Datajud, juscraper, render Quarto) é detalhe de implementação.
"""

from labdados_core.viabilidade.analyze import analyze_form
from labdados_core.viabilidade.render import render_report

__all__ = ["analyze_form", "render_report"]
