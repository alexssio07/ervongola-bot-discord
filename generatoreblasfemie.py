import random
import json

class GeneratoreBlasfemie:
    def __init__(self, data):
        self.bestemmie = data["bestemmie"]  # Carica le frasi dal JSON

    def frase_random(self):
        best = random.choice(self.bestemmie)
        return f"{best['text']}"