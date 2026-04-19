#!/bin/bash
# Fix routing to use WiFi for internet, keep ethernet for local PC connection
# Run this before running detection scripts

echo "Current routes:"
ip route show | grep default

echo ""
echo "Removing bad ethernet default route..."
sudo ip route del default via 192.168.0.2 dev eth0 2>/dev/null || echo "Already removed"

echo ""
echo "New routes:"
ip route show | grep default

echo ""
echo "Testing internet..."
ping -c 2 8.8.8.8 && echo "✓ Internet works!"
