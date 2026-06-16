#!/bin/bash
cd /home/mas/yuna-ai/fish-speech-int4-patch

# Optimizes PyTorch VRAM allocation to prevent fragmentation (helps a ton on 12GB GPUs)
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

/home/mas/yuna-ai/yuna/bin/python tools/run_webui.py \
    --llama-checkpoint-path "checkpoints/s2-pro" \
    --decoder-checkpoint-path "checkpoints/s2-pro/codec.pth" \
    --decoder-config-name modded_dac_vq \
    --device cuda \
    --bnb4 \
    --half \
    --max-seq-len "4096"
