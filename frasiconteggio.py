import random
import json

class FrasiConteggio:
    def __init__(self, data):
        self.frasi = data["frasi"]  # Carica le frasi dal JSON

    def salva_su_file(self, filename):
        # Apro la comunicazione con il file JSON per ottenermi la lista delle frasi
        with open(filename, "w") as file:
            json.dump({"frasi": self.frasi}, file)

    def frase_random(self, utente):
        # Lista dei pesi delle frasi
        pesi = []
        # Calcola il peso per ogni frase
        for frase in self.frasi:
            # Somma di count o del conteggio per tutti gli utenti di ogni frase
            count_totale = sum(user["count"] for user in frase["users"])
            # Calcola il peso basato sulla somma dei count e una costante arbitraria
            peso = 1 / (count_totale + 1)  # +1 per evitare divisione per zero
            pesi.append(peso)

        # Genera un numero casuale basato sui pesi delle frasi
        indice_frase_selezionata = random.choices(range(len(self.frasi)), weights=pesi)[
            0
        ]

        wasFound = False
        for user in self.frasi[indice_frase_selezionata]["users"]:
            # Cerca se l'utente ha già eseguito quella determinata frase corrispondente
            # all'indice generato casualmente
            if user["name"] == utente:
                # Incrementa il valore di count per la frase selezionata
                user["count"] += 1
                self.salva_su_file("frasieffetto.json")
                wasFound = True
                break
            else:
                wasFound = False
        # Se l'utente non ha frasi, aggiungilo per quella specifica frase
        if not (wasFound):
            self.frasi[indice_frase_selezionata]["users"].append(
                {"count": 1, "name": utente}
            )
            # Aggiorna il JSON
            self.salva_su_file("frasieffetto.json")

        # Restituisci la frase selezionata (text) corrispondente all'indice
        return self.frasi[indice_frase_selezionata]["text"]