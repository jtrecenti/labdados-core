"""Formatação de saída de transcrição — TXT / SRT / VTT.

Versão consolidada do que vivia separado em
``services/transcription/main.py`` (com milissegundos, com speaker
opcional) e ``labdados-sdk/src/labdados/transcricao.py`` (sem
milissegundos, sem speaker). Adotamos a versão do serviço como
canônica:

- timestamps SRT/VTT incluem milissegundos (padrão dos formatos);
- ``txt`` aceita ``include_timestamps`` (formato ``[hh:mm:ss]``);
- ``with_speaker=True`` prefixa cada linha com ``[SPEAKER_XX]``.

Quem chamava a versão do SDK ganha precisão de ms no SRT — é mais
detalhado, não quebra parsers.
"""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

OutputFormat = Literal["txt", "srt", "vtt"]


class Segment(TypedDict):
    """Trecho transcrito. ``speaker`` é opcional (presente só em
    diarização)."""

    start: float
    end: float
    text: str
    speaker: NotRequired[str]


def format_timestamp_srt(seconds: float) -> str:
    """``hh:mm:ss,SSS`` (padrão SubRip)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def format_timestamp_vtt(seconds: float) -> str:
    """``hh:mm:ss.SSS`` (padrão WebVTT)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def format_segments(
    segments: list[Segment],
    *,
    output_format: OutputFormat = "srt",
    include_timestamps: bool = True,
    with_speaker: bool = False,
) -> str:
    """Formata uma lista de segmentos.

    Parameters
    ----------
    segments
        Lista de :class:`Segment`. ``end`` ausente em algum item é
        derivado de ``start + 1`` (default conservador).
    output_format
        ``"txt"``, ``"srt"`` ou ``"vtt"``.
    include_timestamps
        Apenas para ``txt``: prefixa cada linha com ``[hh:mm:ss]``.
        Em ``srt``/``vtt`` é sempre incluído (parte obrigatória do
        formato).
    with_speaker
        Se ``True`` e o segmento tem ``speaker``, prefixa o texto com
        ``[SPEAKER_XX] ``.
    """
    if output_format == "txt":
        return _format_txt(segments, include_timestamps=include_timestamps, with_speaker=with_speaker)
    if output_format == "vtt":
        return _format_subtitle(segments, format_ts=format_timestamp_vtt, header="WEBVTT", with_speaker=with_speaker)
    if output_format == "srt":
        return _format_subtitle(segments, format_ts=format_timestamp_srt, header=None, with_speaker=with_speaker)
    raise ValueError(f"output_format desconhecido: {output_format!r}")


def _format_txt(segments: list[Segment], *, include_timestamps: bool, with_speaker: bool) -> str:
    lines: list[str] = []
    for seg in segments:
        prefix = _speaker_prefix(seg, with_speaker)
        text = seg.get("text", "").strip()
        if include_timestamps:
            ts = format_timestamp_srt(seg.get("start", 0.0)).split(",")[0]
            lines.append(f"[{ts}] {prefix}{text}")
        else:
            lines.append(f"{prefix}{text}")
    return "\n".join(lines)


def _format_subtitle(
    segments: list[Segment],
    *,
    format_ts,
    header: str | None,
    with_speaker: bool,
) -> str:
    lines: list[str] = []
    if header:
        lines.append(header)
        lines.append("")
    for i, seg in enumerate(segments, start=1):
        start = seg.get("start", 0.0)
        end = seg.get("end", start + 1.0)
        prefix = _speaker_prefix(seg, with_speaker)
        text = seg.get("text", "").strip()
        lines.append(str(i))
        lines.append(f"{format_ts(start)} --> {format_ts(end)}")
        lines.append(f"{prefix}{text}")
        lines.append("")
    return "\n".join(lines)


def _speaker_prefix(seg: Segment, with_speaker: bool) -> str:
    speaker = seg.get("speaker") if with_speaker else None
    return f"[{speaker}] " if speaker else ""
