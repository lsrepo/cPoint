#!/bin/bash
set -uo pipefail
for year in 2025 2024 2023 2022 2021 2020 2019 2018 2017 2016 2015 2014 2013 2012 2011; do
  echo "=== YEAR $year: fetching ==="
  python3 download_am730_column.py --year "$year"
  echo "=== YEAR $year: repair pass ==="
  python3 download_am730_column.py --year "$year" --repair
  echo "=== YEAR $year: done ==="
done
echo "ALL YEARS DONE"
