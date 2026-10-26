#!/usr/bin/env bash
# Serve any Index-Translate LLM with vLLM (OpenAI-compatible API on :8000).
#
# Usage:
#   ./serve_vllm.sh translate-9b            # general translation, 9B
#   ./serve_vllm.sh translate-35b --tensor-parallel-size 2  # 35B-A3B MoE model
#   ./serve_vllm.sh nailong-9b --tensor-parallel-size 2   # extra args pass through
#   ./serve_vllm.sh homura-2b
#
# Speculative Decoding (MTP) with vLLM:
#   Index-Translate models feature native MTP heads (mtp_num_hidden_layers: 1).
#   To enable MTP acceleration in vLLM, pass:
#     --speculative-config '{"method": "mtp", "num_speculative_tokens": 1}'
#
# Requirements: a vLLM build with Qwen3.5 support (model types
# `qwen3_5` / `qwen3_5_text`). Install e.g.:
#   pip install -U vllm        # recent release; we test with cu129 builds
#
# GPU memory guide (bf16, single card):
#   2B models: ~8 GB    9B models: ~24 GB   35B MoE: ~70 GB (recommend --tensor-parallel-size 2)
#   Nailong 9B: the shipped config caps position embeddings at 229376;
#   reduce --max-model-len for lower KV-cache memory use.

set -euo pipefail

which="${1:-}"; shift || true
MAXLEN=32768
case "$which" in
  translate-2b)  MODEL=IndexTeam/Index-Translate-2B ;;
  translate-9b)  MODEL=IndexTeam/Index-Translate-9B ;;
  translate-35b) MODEL=IndexTeam/Index-Translate-35B-A3B-preview ;;
  nailong-2b)    MODEL=IndexTeam/Index-Nailong-2B;  MAXLEN=262144 ;;
  nailong-9b)    MODEL=IndexTeam/Index-Nailong-9B;  MAXLEN=229376 ;;  # shipped config cap
  homura-2b)     MODEL=IndexTeam/Index-Homura-2B ;;
  homura-9b)     MODEL=IndexTeam/Index-Homura-9B ;;
  *)
    echo "usage: $0 {translate-2b|translate-9b|translate-35b|nailong-2b|nailong-9b|homura-2b|homura-9b} [extra vllm args]" >&2
    exit 2
    ;;
esac

echo "serving $MODEL on :8000 (max-model-len $MAXLEN, extra args: $*)" >&2
exec vllm serve "$MODEL" \
  --served-model-name "$MODEL" \
  --max-model-len "$MAXLEN" \
  "$@"
