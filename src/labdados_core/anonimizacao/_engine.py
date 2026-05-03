"""Wrapper do modelo HF ``openai/privacy-filter`` para token classification.

O modelo emite um label BIOES por subtoken. Este módulo:

1. Tokeniza o texto com ``return_offsets_mapping=True``.
2. Roda inference (CPU ou CUDA, ditado pelo caller).
3. Converte os labels por subtoken em spans contíguos no texto
   original, agrupando ``B-/I-/E-/S-`` por categoria.
4. Devolve ``list[(start, end, label, texto)]`` — offsets em chars
   sobre o texto original (não sobre tokens).

O modelo é carregado uma única vez por processo (cache via lru_cache).
Em produção o serviço sobe um worker; em modo SDK local o usuário
final não paga o custo de carga repetidamente.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

from labdados_core.anonimizacao.exceptions import ModeloIndisponivel

if TYPE_CHECKING:  # pragma: no cover — apenas type hints
    pass

log = logging.getLogger(__name__)

# Tamanho máximo de janela do modelo. O modelo aceita 128k, mas o tokenizer
# do HF e a memória do dispositivo são quem mandam. Quebrar em janelas
# de 2k subtokens com overlap de 128 cobre textos longos sem estourar VRAM.
_WINDOW = 2048
_OVERLAP = 128


def _resolve_device(use_gpu: bool) -> str:
    """Escolhe o device. Se ``use_gpu=True`` mas CUDA indisponível, cai pra CPU com aviso."""
    try:
        import torch
    except ImportError as exc:
        raise ModeloIndisponivel(
            "torch não instalado. Use o extra apropriado: "
            "`labdados-core[anonimizacao-cpu]` ou `labdados-core[anonimizacao-gpu]`."
        ) from exc

    if use_gpu and torch.cuda.is_available():
        return "cuda"
    if use_gpu:
        log.warning("use_gpu=True mas CUDA indisponível; rodando em CPU.")
    return "cpu"


@lru_cache(maxsize=2)
def _load_pipeline(modelo: str, device: str):
    """Carrega tokenizer + modelo. Cacheado por (modelo, device).

    Lazy import de ``transformers``/``torch`` — se o caller só usa
    :mod:`labdados_core.anonimizacao.strategies`, ele não paga o custo
    nem precisa instalar essas deps.
    """
    try:
        import torch
        from transformers import AutoModelForTokenClassification, AutoTokenizer
    except ImportError as exc:  # pragma: no cover
        raise ModeloIndisponivel(
            "transformers não instalado. Use `labdados-core[anonimizacao-cpu]` "
            "ou `labdados-core[anonimizacao-gpu]`."
        ) from exc

    log.info("Carregando modelo de anonimização %s em %s...", modelo, device)
    tokenizer = AutoTokenizer.from_pretrained(modelo)
    dtype = torch.float16 if device == "cuda" else torch.float32
    model = AutoModelForTokenClassification.from_pretrained(modelo, torch_dtype=dtype)
    model = model.to(device)
    model.eval()
    log.info("Modelo carregado.")
    return tokenizer, model, device


def detectar_pii(
    texto: str,
    *,
    modelo: str = "openai/privacy-filter",
    use_gpu: bool = False,
    threshold: float = 0.0,
) -> list:
    """Roda o modelo no texto e devolve lista de spans PII.

    Cada item é uma 4-tupla nomeada via ``_Span`` em
    :mod:`labdados_core.anonimizacao.strategies` (``start``, ``end``,
    ``label``, ``texto``). Offsets são em chars sobre o texto original.
    """
    from labdados_core.anonimizacao.strategies import _Span

    if not texto.strip():
        return []

    device = _resolve_device(use_gpu)
    tokenizer, model, _ = _load_pipeline(modelo, device)

    import torch

    encoding = tokenizer(
        texto,
        return_offsets_mapping=True,
        return_tensors="pt",
        truncation=False,
        add_special_tokens=False,
    )
    offsets = encoding.pop("offset_mapping")[0].tolist()
    input_ids = encoding["input_ids"][0]
    n_tokens = input_ids.shape[0]

    if n_tokens == 0:
        return []

    id2label = model.config.id2label
    all_label_ids: list[int] = []
    all_scores: list[float] = []

    # Janelas com overlap pra textos longos.
    step = _WINDOW - _OVERLAP
    pos = 0
    while pos < n_tokens:
        end = min(pos + _WINDOW, n_tokens)
        window_ids = input_ids[pos:end].unsqueeze(0).to(device)
        with torch.no_grad():
            logits = model(input_ids=window_ids).logits[0]
        if threshold > 0:
            probs = torch.softmax(logits, dim=-1)
            scores, label_ids = probs.max(dim=-1)
            scores_list = scores.cpu().tolist()
            label_ids_list = label_ids.cpu().tolist()
        else:
            label_ids_list = logits.argmax(dim=-1).cpu().tolist()
            scores_list = [1.0] * len(label_ids_list)

        # Aproveitar só a parte "nova" da janela quando há overlap.
        keep_from = 0 if pos == 0 else _OVERLAP // 2
        if pos == 0:
            all_label_ids.extend(label_ids_list)
            all_scores.extend(scores_list)
        else:
            # Já gravamos todos os tokens até pos+keep_from-1 na janela anterior;
            # adicionar a partir de keep_from da janela atual.
            already = len(all_label_ids) - pos
            start_idx = max(already, keep_from)
            all_label_ids.extend(label_ids_list[start_idx:])
            all_scores.extend(scores_list[start_idx:])
        pos = end if end == n_tokens else pos + step

    # Trim caso tenha vazado por arredondamento.
    all_label_ids = all_label_ids[:n_tokens]
    all_scores = all_scores[:n_tokens]

    spans: list[_Span] = []
    cur_label: str | None = None
    cur_start: int | None = None
    cur_end: int | None = None

    def _flush():
        nonlocal cur_label, cur_start, cur_end
        if cur_label is not None and cur_start is not None and cur_end is not None:
            spans.append(
                _Span(
                    start=cur_start,
                    end=cur_end,
                    label=cur_label,
                    texto=texto[cur_start:cur_end],
                )
            )
        cur_label = cur_start = cur_end = None

    for i, (label_id, (off_s, off_e)) in enumerate(zip(all_label_ids, offsets)):
        label = id2label.get(int(label_id), "O") if isinstance(id2label, dict) else id2label[int(label_id)]
        score = all_scores[i] if i < len(all_scores) else 1.0
        if label == "O" or off_s == off_e or score < threshold:
            _flush()
            continue
        # Labels esperados: "B-private_person", "I-private_person", "E-...", "S-..."
        if "-" in label:
            prefix, cat = label.split("-", 1)
        else:
            prefix, cat = "S", label

        if prefix in ("B", "S"):
            _flush()
            cur_label = cat
            cur_start = off_s
            cur_end = off_e
        elif prefix in ("I", "E") and cur_label == cat:
            cur_end = off_e
        else:
            # I/E sem B prévio do mesmo cat — trata como início mesmo assim.
            _flush()
            cur_label = cat
            cur_start = off_s
            cur_end = off_e

    _flush()
    return spans
