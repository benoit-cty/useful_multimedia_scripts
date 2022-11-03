# GPIO 35 et 34 ne supporte pas Output
# 12 empêche le démarrage
# 0, 2, 4 is a Strapping PIN and should be avoided.
# 16 pose problème aussi.
# 23 ne fonctionne pas
for i, gpio in enumerate([13,14,27,23,25,33,32, 17]):
    print(f'''  - platform: gpio
    pin: {gpio}
    name: "relais_{i+1}-gpio{gpio}"
    inverted: true''')