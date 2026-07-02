#!/usr/bin/env bash
set -e

for n in 225 228; do
  if [ ! -d "/sys/class/gpio/gpio$n" ]; then
    echo "$n" > /sys/class/gpio/export
  fi
  echo in > "/sys/class/gpio/gpio$n/direction"
done

echo "buttons gpio ready: 225=capture, 228=video"
