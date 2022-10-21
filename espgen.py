for i, gpio in enumerate([13,12,14,27,26,25,33,32]):
    print(f'''  - platform: gpio
    pin: {gpio}
    name: "gpio{gpio}-{i+1}"''')