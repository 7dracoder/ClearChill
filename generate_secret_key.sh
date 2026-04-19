#!/bin/bash
# Generate a secure SECRET_KEY for ClearChill deployment

echo "═══════════════════════════════════════════════════════════════"
echo "  CLEARCHILL - SECRET KEY GENERATOR"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Generating secure SECRET_KEY..."
echo ""

SECRET_KEY=$(openssl rand -hex 32)

echo "✅ Your SECRET_KEY:"
echo ""
echo "$SECRET_KEY"
echo ""
echo "Copy this value and add it to Render.com environment variables"
echo ""
echo "═══════════════════════════════════════════════════════════════"
