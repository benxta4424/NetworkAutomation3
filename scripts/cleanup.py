import subprocess

print("🧹 CLEANING ALL 192.168.x.x ROUTES...")

# Delete all 192.168.x.x routes
result = subprocess.run(
    "sudo ip route show | grep '192.168.' | grep 'via' | sudo xargs -I {} ip route del {}",
    shell=True,
    capture_output=True,
    text=True
)

print(f"✅ Cleanup command executed (return code: {result.returncode})")

# Show current routes
print("📋 CURRENT ROUTING TABLE:")
subprocess.run(["ip", "route", "show"])