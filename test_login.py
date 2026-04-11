import requests

s = requests.Session()

# Test OTP
res = s.post('http://127.0.0.1:8000/send-otp', json={"contact": "manavchauhan0442@gmail.com"})
print("send-otp:", res.json())

# Wait, the app needs to be running.
