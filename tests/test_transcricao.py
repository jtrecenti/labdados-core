"""Tests dos formatters de transcrição (puros, sem dependência de modelo)."""

from __future__ import annotations

import pytest

from labdados_core.transcricao import (
    Segment,
    format_segments,
    format_timestamp_srt,
    format_timestamp_vtt,
)

# ---------------------------------------------------------------------------
# format_timestamp_*
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "secs, expected",
    [
        (0.0, "00:00:00,000"),
        (1.5, "00:00:01,500"),
        (61.0, "00:01:01,000"),
        (3661.123, "01:01:01,123"),
    ],
)
def test_format_timestamp_srt(secs, expected):
    assert format_timestamp_srt(secs) == expected


@pytest.mark.parametrize(
    "secs, expected",
    [
        (0.0, "00:00:00.000"),
        (1.5, "00:00:01.500"),
        (3661.123, "01:01:01.123"),
    ],
)
def test_format_timestamp_vtt(secs, expected):
    assert format_timestamp_vtt(secs) == expected


# ---------------------------------------------------------------------------
# format_segments — txt
# ---------------------------------------------------------------------------


def _segs() -> list[Segment]:
    return [
        {"start": 0.0, "end": 2.5, "text": "Olá."},
        {"start": 2.5, "end": 5.0, "text": "Tudo bem?"},
    ]


def test_format_txt_with_timestamps_default():
    out = format_segments(_segs(), output_format="txt")
    assert out == "[00:00:00] Olá.\n[00:00:02] Tudo bem?"


def test_format_txt_without_timestamps():
    out = format_segments(_segs(), output_format="txt", include_timestamps=False)
    assert out == "Olá.\nTudo bem?"


def test_format_txt_with_speaker():
    segs: list[Segment] = [
        {"start": 0.0, "end": 1.0, "text": "Oi.", "speaker": "SPEAKER_00"},
        {"start": 1.0, "end": 2.0, "text": "Tchau."},  # sem speaker
    ]
    out = format_segments(segs, output_format="txt", with_speaker=True, include_timestamps=False)
    assert out == "[SPEAKER_00] Oi.\nTchau."


def test_format_txt_speaker_only_when_flag_on():
    segs: list[Segment] = [
        {"start": 0.0, "end": 1.0, "text": "X", "speaker": "SPEAKER_00"},
    ]
    out = format_segments(segs, output_format="txt", with_speaker=False, include_timestamps=False)
    assert out == "X"


# ---------------------------------------------------------------------------
# format_segments — srt
# ---------------------------------------------------------------------------


def test_format_srt_basic():
    out = format_segments(_segs(), output_format="srt")
    expected = (
        "1\n"
        "00:00:00,000 --> 00:00:02,500\n"
        "Olá.\n"
        "\n"
        "2\n"
        "00:00:02,500 --> 00:00:05,000\n"
        "Tudo bem?\n"
    )
    assert out == expected


def test_format_srt_with_speaker():
    segs: list[Segment] = [
        {"start": 0.0, "end": 1.0, "text": "Oi", "speaker": "SPEAKER_01"},
    ]
    out = format_segments(segs, output_format="srt", with_speaker=True)
    assert "[SPEAKER_01] Oi" in out


def test_format_srt_missing_end_uses_start_plus_1():
    segs: list[Segment] = [{"start": 5.0, "text": "fim"}]  # type: ignore[typeddict-item]
    out = format_segments(segs, output_format="srt")
    assert "00:00:05,000 --> 00:00:06,000" in out


# ---------------------------------------------------------------------------
# format_segments — vtt
# ---------------------------------------------------------------------------


def test_format_vtt_starts_with_header_and_uses_dot_separator():
    out = format_segments(_segs(), output_format="vtt")
    assert out.startswith("WEBVTT\n\n")
    assert "00:00:02.500 --> 00:00:05.000" in out


def test_format_vtt_with_speaker():
    segs: list[Segment] = [
        {"start": 0.0, "end": 1.0, "text": "Bom dia", "speaker": "SPEAKER_00"},
    ]
    out = format_segments(segs, output_format="vtt", with_speaker=True)
    assert "[SPEAKER_00] Bom dia" in out


# ---------------------------------------------------------------------------
# format_segments — erros
# ---------------------------------------------------------------------------


def test_format_segments_unknown_format_raises():
    with pytest.raises(ValueError, match="output_format desconhecido"):
        format_segments(_segs(), output_format="json")  # type: ignore[arg-type]


def test_format_segments_empty_list():
    assert format_segments([], output_format="txt") == ""
    srt = format_segments([], output_format="srt")
    assert srt == ""
    vtt = format_segments([], output_format="vtt")
    assert vtt == "WEBVTT\n"
