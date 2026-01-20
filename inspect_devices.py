import sounddevice as sd

print(f"{'ID':<4} {'HostAPI':<8} {'Name'}")
print("-" * 50)
for i, device in enumerate(sd.query_devices()):
    if device['max_output_channels'] > 0:
        print(f"{i:<4} {device['hostapi']:<8} '{device['name']}'")
