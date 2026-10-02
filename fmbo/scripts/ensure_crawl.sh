#!/bin/bash
# Watchdog: ensure the FMBO people crawl is running or complete.
# Prints one line: COMPLETE <n> | RUNNING <n>/<target> | RELAUNCHED <n>/<target>
cd ~/workspace/movies/fmbo || exit 1
TARGET=7114
COUNT=$(ls people/*.json 2>/dev/null | wc -l)
if [ "$COUNT" -ge "$TARGET" ]; then
  echo "COMPLETE $COUNT"
  exit 0
fi
if pgrep -f "python3 crawl_people.py" > /dev/null; then
  echo "RUNNING $COUNT/$TARGET"
  exit 0
fi
# dead: relaunch (resumable, skips existing files)
cd scripts || exit 1
setsid nohup python3 crawl_people.py >> ../crawl_people.out 2>&1 < /dev/null > /dev/null 2>&1 &
echo "RELAUNCHED $COUNT/$TARGET"
