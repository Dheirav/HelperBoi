#!/bin/bash
# Progress for a unittest run started as:
#   tools/run-tests.sh test_adversarial        (writes .test-run/<name>.log, .start, .total)
# Shows done of total, elapsed and an ETA from the measured rate. No ETA until at
# least 5 tests have finished, because one or two slow tests make the rate meaningless.
# Usage: tools/test-progress.sh [name] [--watch]
cd "$(dirname "$0")/.."
name=test_adversarial; watch=0
for a in "$@"; do case $a in --watch) watch=1;; *) name=$a;; esac; done
d=.test-run
show() {
  [ -f $d/$name.log ] || { echo "no run found for $name"; return 1; }
  total=$(tail -1 $d/$name.total); start=$(cat $d/$name.start)
  done_n=$(grep -cE '(\.\.\. |^)(ok|FAIL|ERROR|skipped.*)$' $d/$name.log)
  bad=$(grep -cE '(\.\.\. |^)(FAIL|ERROR)$' $d/$name.log)
  now=$(date +%s); [ -f $d/$name.exit ] && now=$(date -r $d/$name.exit +%s); el=$((now-start))
  fin=""; [ -f $d/$name.exit ] && fin=" | FINISHED exit=$(cat $d/$name.exit)"
  line="$name: $done_n/$total done, $bad failed/errored, elapsed ${el}s"
  if [ -z "$fin" ] && [ "$done_n" -ge 5 ] && [ "$el" -gt 0 ]; then
    rem=$(( (total-done_n)*el/done_n ))
    eta=$(TZ=Asia/Kolkata date -d "@$((now+rem))" '+%H:%M:%S IST')
    line="$line | rate $(awk "BEGIN{printf \"%.2f\",$done_n/$el}") tests/s | ETA $eta (about ${rem}s)"
  elif [ -z "$fin" ]; then line="$line | no ETA yet (fewer than 5 finished)"; fi
  echo "$line$fin"
}
if [ $watch = 1 ]; then while true; do show; [ -f $d/$name.exit ] && break; sleep 5; done; else show; fi
