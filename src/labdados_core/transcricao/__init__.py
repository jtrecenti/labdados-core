"""Helpers compartilhados para o pipeline de transcrição.

A v0.9.0 cobre apenas a parte que estava genuinamente duplicada entre
SDK e serviço: formatação de timestamps (SRT/VTT) e de segmentos
(TXT/SRT/VTT, com ou sem speaker, com ou sem timestamps inline).

O **engine de transcrição** (faster-whisper, WhisperX, pyannote para
diarização, chunking ffmpeg para OOM-protection) continua em
``services/transcription`` e em ``labdados.transcricao``: cada lado tem
complexidade própria que justifica não unificar agora. Se aparecer
divergência real de comportamento, abrir um subpacote
``labdados_core.transcricao._engines/`` seguindo o padrão de OCR.

API:

- :class:`Segment` — TypedDict com ``start``, ``end``, ``text`` e
  opcional ``speaker``. Formato comum entre engines.
- :func:`format_timestamp_srt` / :func:`format_timestamp_vtt` —
  ``hh:mm:ss,SSS`` / ``hh:mm:ss.SSS``.
- :func:`format_segments` — devolve string única no formato pedido
  (``txt`` / ``srt`` / ``vtt``).
"""

from labdados_core.transcricao.formatters import (
    Segment,
    format_segments,
    format_timestamp_srt,
    format_timestamp_vtt,
)

__all__ = [
    "Segment",
    "format_segments",
    "format_timestamp_srt",
    "format_timestamp_vtt",
]
