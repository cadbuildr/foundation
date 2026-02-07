"""
WebRTC Demo Script - Demonstrates cube creation and color changes

This script creates a cube and changes its color several times to demonstrate
the WebRTC communication between foundation and the viewer via the broker.

Usage:
    1. Start the Next.js hub: cd tsjs && pnpm dev
    2. Start the broker: cd py/packages/broker && poetry run cadbuildr-broker
    3. Open viewer in browser: http://localhost:3000/viewer
    4. Run this script: poetry run python tests/examples/webrtc_demo.py
"""

from cadbuildr.foundation import *
import time

print("=" * 60)
print("WebRTC Demo - Cube with Color Changes")
print("=" * 60)
print()
print("Make sure you have:")
print("1. Next.js hub running (http://localhost:3000)")
print("2. Broker running (cadbuildr-broker)")
print("3. Viewer page open in browser (http://localhost:3000/viewer)")
print()
print("=" * 60)
print()

# Create cube
print("Creating cube...")
cube = Part()
s = Sketch(cube.xy())
square = Square.from_center_and_side(s.origin, 1)
e = Extrusion(square, 1)
cube.add_operation(e)

# Show initial cube (default color)
print("Showing initial cube...")
show(cube)
print("Waiting 3 seconds...")
time.sleep(3)

# Change color to red
print("\nChanging color to RED...")
cube.paint("red")
show(cube)
print("Waiting 3 seconds...")
time.sleep(3)

# Change color to blue
print("\nChanging color to BLUE...")
cube.paint("blue")
show(cube)
print("Waiting 3 seconds...")
time.sleep(3)

# Change color to green
print("\nChanging color to GREEN...")
cube.paint("green")
show(cube)
print("Waiting 3 seconds...")
time.sleep(3)

# Change color to yellow
print("\nChanging color to YELLOW...")
cube.paint("yellow")
show(cube)
print("Waiting 3 seconds...")
time.sleep(3)

# Change color to purple
print("\nChanging color to PURPLE...")
cube.paint("purple")
show(cube)

print("\n" + "=" * 60)
print("Demo complete!")
print("=" * 60)












