#!/usr/bin/env bash
set -u
if ! command -v s3270 >/dev/null 2>&1; then
  echo "SKIP: s3270 is not installed; command-mode IND\$FILE validation assets are present."
  exit 0
fi
log="s3270_indfile_validation.log"
: > "$log"
for script in manual_validation/s3270_indfile_get.scr manual_validation/s3270_indfile_put.scr manual_validation/s3270_indfile_roundtrip.scr manual_validation/s3270_indfile_sensitive_dataset.scr; do
  echo "RUN $script" | tee -a "$log"
  s3270 -script < "$script" >> "$log" 2>&1 || { echo "FAIL $script" | tee -a "$log"; exit 1; }
done
echo "PASS: s3270 command-mode IND\$FILE validation completed" | tee -a "$log"
