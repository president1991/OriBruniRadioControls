import serial

print("Apro COM5…")
s = serial.Serial("COM5", 115200, timeout=1)
print("Porta aperta:", s.is_open)
s.close()
print("Porta chiusa.")