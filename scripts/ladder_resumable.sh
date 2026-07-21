#!/bin/bash
# Resume-safe extractor ladder + judge rescoring.
# Re-running skips any rung/judge already completed (marker files), so a
# reboot or Ctrl-C only ever loses the rung in flight, never finished work.
cd /home/mas/yuna-ai
LADDER=data/bench_results/ladder
mkdir -p $LADDER
LOG=$LADDER/run.log
GEMMA="hf.co/HauhauCS/Gemma4-12B-QAT-Uncensored-HauhauCS-Balanced:Q4_K_M"

echo "=== LADDER (resumable) START $(date) ===" >> $LOG
for m in qwen2.5:3b qwen2.5:7b qwen2.5:14b; do
  marker="$LADDER/.done_$(echo $m | tr ':/' '__')"
  if [ -f "$marker" ]; then
    echo "--- skip $m (already done) ---" >> $LOG; continue
  fi
  echo "--- extractor: $m $(date) ---" >> $LOG
  if .venv/bin/yuna bench --strategy agentic --conversations 0 --model "$m" --qa-model "$GEMMA" \
       --out "$LADDER" 2>&1 | grep -E "Bench start|Bench done" | tail -3 >> $LOG; then
    # mark done only if a summary.json landed for this rung
    latest=$(ls -dt $LADDER/run_*_agentic 2>/dev/null | head -1)
    [ -f "$latest/summary.json" ] && touch "$marker" && echo "  marked $m done" >> $LOG
  fi
done

echo "=== JUDGE all runs (strategies + ladder) $(date) ===" >> $LOG
for r in data/bench_results/run_2026*/results.jsonl $LADDER/run_2026*/results.jsonl; do
  [ -f "$r" ] || continue
  [ -f "$(dirname $r)/summary_judged.json" ] && continue   # already judged
  echo "--- judging: $r $(date) ---" >> $LOG
  .venv/bin/python -m yuna.bench.judge "$r" 2>&1 | tail -2 >> $LOG
done
echo "=== ALL COMPLETE $(date) ===" >> $LOG
