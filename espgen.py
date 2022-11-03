# GPIO 35 et 34 ne supporte pas Output
# GPIO 12 empêche le démarrage
# GPIO2, GPIO0, GPIO4 is a Strapping PIN and should be avoided.
# 16 pose problème aussi.
for i, gpio in enumerate([13,14,27,23,25,33,32, 17]):
    print(f'''  - platform: gpio
    pin: {gpio}
    name: "relais_{i+1}-gpio{gpio}"
    inverted: true''')