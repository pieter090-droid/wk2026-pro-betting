import os
import json

root_dir = './data'
print(f"Start met scannen van map: {root_dir}")

for root, dirs, files in os.walk(root_dir):
    for file in files:
        print(f"Gevonden bestand: {file} in map {root}")

print("Scan voltooid.")
