import sounddevice as sd

print(f"{'ID':<4} {'Name'}")
print("-" * 20)
for i, api in enumerate(sd.query_hostapis()):
    print(f"{i:<4} '{api['name']}'")
