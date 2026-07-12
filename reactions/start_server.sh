#!/bin/bash
cd /home/mas/yuna-ai/fish-speech-int4-patch

# PyTorch VRAM allocation tuning
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

/home/mas/yuna-ai/yuna/bin/python tools/api_server.py \
    --llama-checkpoint-path "checkpoints/s2-pro" \
    --decoder-checkpoint-path "checkpoints/s2-pro/codec.pth" \
    --decoder-config-name modded_dac_vq \
    --device cuda \
    --bnb4 \
    --lazy-load \
    --idle-timeout-seconds "300" \
    --max-seq-len "3072" \
    --listen "0.0.0.0:8880"
