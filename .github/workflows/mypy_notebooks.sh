#!/bin/bash
FAILED=0

while IFS= read -r nb; do
  [[ -z "$nb" || ! -f "$nb" ]] && continue
  if git check-ignore -q "$nb"; then
    echo -e "\033[90m=== Skipped $nb (gitignore) ===\033[0m"
    continue
  fi
  
  
  NB_DIR=$(dirname "$nb")
  NB_BASE=$(basename "$nb" .ipynb)
  PY_FILE="${NB_DIR}/_${NB_BASE}.py"
  
  echo "=== Checking $nb -> $PY_FILE ==="

  # Convert to _ prefixed filename (simple!)
  jupyter nbconvert --to python "$nb" \
    --output "_${NB_BASE}" \
    --log-level ERROR
  
  if ! uv run mypy "$PY_FILE" --config-file pyproject.toml; then
    ((FAILED++))
  fi
  
  rm -f "$PY_FILE"
done < <(find . -name "*.ipynb")

if [ $FAILED -eq 0 ]; then
  echo "🎉 All notebooks passed mypy!"
  exit 0
else
  echo "❌ $FAILED notebooks failed mypy!"
  exit 1
fi
