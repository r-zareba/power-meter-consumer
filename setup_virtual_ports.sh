#!/bin/bash
# Virtual Serial Port Setup for STM32 Simulator Testing
#
# This script creates a pair of virtual serial ports that are connected together.
# The simulator writes to one port, and your receiver reads from the other.

echo "Setting up virtual serial ports for testing..."
echo ""

# Check if socat is installed
if ! command -v socat &> /dev/null; then
    echo "ERROR: socat is not installed"
    echo ""
    echo "Install it with:"
    echo "  Ubuntu/Debian: sudo apt-get install socat"
    echo "  macOS: brew install socat"
    echo "  Fedora: sudo dnf install socat"
    exit 1
fi

echo "Creating virtual serial port pair..."
echo ""
echo "This will create two connected virtual serial ports:"
echo "  /dev/pts/X ← Simulator writes here"
echo "  /dev/pts/Y ← Receiver reads here"
echo ""
echo "The port numbers will be shown below."
echo "Press Ctrl+C to stop and remove the virtual ports."
echo ""
echo "Starting socat..."
echo "----------------------------------------"

# Create virtual serial port pair
# -d -d: verbose output showing port names
socat -d -d pty,raw,echo=0 pty,raw,echo=0
