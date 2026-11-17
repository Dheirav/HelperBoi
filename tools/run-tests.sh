#!/bin/bash
# Run one unittest module in the background with a log the progress reader can parse.
#   tools/run-tests.sh test_adversarial && tools/test-progress.sh --watch
# Uses .venv/bin/python by path, never a bare python3.
cd "$(dirname "$0")/.."
name=${1:-test_adversarial}; d=.test-run; mkdir -p $d
rm -f $d/$name.exit
.venv/bin/python -c "import unittest;print(unittest.defaultTestLoader.loadTestsFromName('$name').countTestCases())" 2>/dev/null | tail -1 > $d/$name.total
date +%s > $d/$name.start
( .venv/bin/python -m unittest $name -v > $d/$name.log 2>&1; echo $? > $d/$name.exit ) &
echo "started $name: $(cat $d/$name.total) tests"
