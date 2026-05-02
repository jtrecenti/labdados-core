"""Exceções específicas do pipeline de OCR."""


class EngineUnavailable(RuntimeError):
    """Engine de OCR pedido não está instalado neste ambiente.

    Tipicamente significa que falta o extra ``[ocr-cpu]`` ou
    ``[ocr-gpu]`` no ``pip install``. A mensagem inclui qual extra
    instalar.
    """


class TesseractNotFound(RuntimeError):
    """O binário ``tesseract`` não está no PATH (nem nos lugares
    convencionais).

    Diferente de :class:`EngineUnavailable`, aqui o pacote Python está
    instalado — falta apenas o binário do OS. A mensagem inclui dicas
    de onde instalar.
    """
