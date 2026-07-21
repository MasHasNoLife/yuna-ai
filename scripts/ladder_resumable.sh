#!/bin/bash
# Resume-safe, pausable extractor ladder + judge rescoring.
#
#   scripts/ladder_resumable.sh          # run all remaining rungs, then judge
#   scripts/ladder_resumable.sh one      # run ONLY the next pending rung, then stop
#   scripts/ladder_resumable.sh judge    # just (re)judge any unjudged runs
#
# Each model's results + summary are saved the instant that rung finishes, and a
# marker file is written so it's never redone. Safe to Ctrl-C or reboot between
# rungs — you lose only the rung in flight. Run it again anytime to continue.
cd /home/mas/yuna-ai || exit 1
LADDER=data/bench_results/ladder
mkdir -p $LADDER
LOG=$LADDER/run.log
GEMMA="hf.co/HauhauCS/Gemma4-12B-QAT-Uncensored-HauhauCS-Balanced:Q4_K_M"
MODELS=(qwen2.5:3b qwen2.5:7b qwen2.5:14b)
MODE="${1:-all}"

run_rung() {
  local m="$1"
  local marker="$LADDER/.done_$(echo "$m" | tr ':/' '__')"
  [ -f "$marker" ] && { echo "--- skip $m (done) ---" >> $LOG; return 2; }
  echo "--- extractor: $m $(date) ---" >> $LOG
  .venv/bin/yuna bench --strategy agentic --conversations 0 --model "$m" \
      --qa-model "$GEMMA" --out "$LADDER" 2>&1 | grep -E "Bench start|Bench done" | tail -3 >> $LOG
  local latest
  latest=$(ls -dt $LADDER/run_*_agentic 2>/dev/null | head -1)
  if [ -f "$latest/summary.json" ]; then
    touch "$marker"; echo "  SAVED + marked $m done $(date)" >> $LOG; return 0
  fi
  echo "  WARNING: $m produced no summary — not marked, will retry next run" >> $LOG; return 1
}

judge_all() {
  echo "=== JUDGE unjudged runs $(date) ===" >> $LOG
  for r in data/bench_results/run_2026*/results.jsonl $LADDER/run_2026*/results.jsonl; do
    [ -f "$r" ] || continue
    [ -f "$(dirname "$r")/summary_judged.json" ] && continue
    echo "--- judging: $r ---" >> $LOG
    .venv/bin/python -m yuna.bench.judge "$r" 2>&1 | tail -2 >> $LOG
  done
}

echo "=== LADDER ($MODE) START $(date) ===" >> $LOG
case "$MODE" in
  judge) judge_all ;;
  one)
    for m in "${MODELS[@]}"; do
      run_rung "$m"; rc=$?
      [ $rc -eq 0 ] && { echo "=== stopped after $m (pausable mode) $(date) ===" >> $LOG; exit 0; }
      [ $rc -eq 1 ] && exit 1   # failed rung, stop
    done
    echo "=== all rungs already done; judging ===" >> $LOG; judge_all ;;
  *)
    for m in "${MODELS[@]}"; do run_rung "$m"; [ $? -eq 1 ] && exit 1; done
    judge_all ;;
esac
echo "=== DONE ($MODE) $(date) ===" >> $LOG
