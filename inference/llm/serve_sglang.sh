#!/usr/bin/env bash
# Serve any Index-Translate LLM with SGLang (OpenAI-compatible API on :30000).
#
# Usage:
#   ./serve_sglang.sh translate-9b                  # standard autoregressive serving
#   ./serve_sglang.sh translate-9b --mtp            # with native MTP speculative decoding (~20-30% speedup)
#   ./serve_sglang.sh translate-35b --tp 2 --mtp    # 35B-A3B MoE model with TP=2 and MTP
#   ./serve_sglang.sh translate-2b                  # 2B model
#   ./serve_sglang.sh homura-9b --mtp               # Homura model with MTP
#
# Speculative Decoding (MTP) Notes:
#   Index-Translate models ship with native Multi-Token Prediction (MTP) heads
#   directly in the checkpoint weights (mtp_num_hidden_layers: 1).
#   When --mtp is specified, SGLang uses the model's own MTP layers as the draft model
#   via the NEXTN speculative decoding algorithm, providing ~20%-30% faster decode
#   throughput without requiring an external draft model or losing quality.
#
# Requirements:
#   pip install sglang
#
# GPU memory guide (bf16):
#   2B models:  ~8 GB (1 card)
#   9B models:  ~24 GB (1 card)
#   35B MoE:    ~70 GB (recommended --tp 2 across 2 cards)

set -euo pipefail

which="${1:-}"; shift || true

ENABLE_MTP=false
EXTRA_ARGS=()

for arg in "$@"; do
  if [ "$arg" = "--mtp" ]; then
    ENABLE_MTP=true
  else
    EXTRA_ARGS+=("$arg")
  fi
done

case "$which" in
  translate-2b)  MODEL=IndexTeam/Index-Translate-2B ;;
  translate-9b)  MODEL=IndexTeam/Index-Translate-9B ;;
  translate-35b) MODEL=IndexTeam/Index-Translate-35B-A3B-preview ;;
  nailong-2b)    MODEL=IndexTeam/Index-Nailong-2B ;;
  nailong-9b)    MODEL=IndexTeam/Index-Nailong-9B ;;
  homura-2b)     MODEL=IndexTeam/Index-Homura-2B ;;
  homura-9b)     MODEL=IndexTeam/Index-Homura-9B ;;
  *)
    echo "usage: $0 {translate-2b|translate-9b|translate-35b|nailong-2b|nailong-9b|homura-2b|homura-9b} [--mtp] [extra sglang args]" >&2
    exit 2
    ;;
esac

CMD=(
  python3 -m sglang.launch_server
  --model-path "$MODEL"
  --served-model-name "$MODEL"
  --port 30000
  --host 0.0.0.0
  --trust-remote-code
  --mamba-scheduler-strategy extra_buffer
)

if [ "$ENABLE_MTP" = true ]; then
  echo "Enabling native MTP speculative decoding (NEXTN)..." >&2
  export SGLANG_ENABLE_SPEC_V2=1
  CMD+=(
    --speculative-algorithm NEXTN
    --speculative-draft-model-path "$MODEL"
    --speculative-num-steps 1
    --speculative-eagle-topk 1
    --speculative-num-draft-tokens 2
  )
fi

echo "serving $MODEL on :30000 (MTP: $ENABLE_MTP, extra args: ${EXTRA_ARGS[*]:-none})" >&2
exec "${CMD[@]}" "${EXTRA_ARGS[@]}"
