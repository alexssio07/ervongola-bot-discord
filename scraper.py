import requests
from bs4 import BeautifulSoup
import re

urlAmazon = (
    "https://www.amazon.it/OPPO-Smartphone-fotocamera-Supporto-Versione/dp/B0DCBCJHD4"
)


def scraper(url):
    # Definisci l'header per evitare di essere bloccato
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }

    # Effettua la richiesta
    response = requests.get(url, headers=headers)

    # Verifica se la richiesta è andata a buon fine
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, "html.parser")
        if "amazon" in url:
            # Estrazione valori da proprietà HTML con la funzione find("tag HTML", {"attributo": "valore"})
            title = soup.find("span", {"id": "productTitle"})
            if title:
                title = title.get_text(strip=True)
            else:
                title = "N/A"

            # Estrai il prezzo del prodotto
            price = soup.find("span", {"class": "a-price-whole"})
            if price:
                price = price.get_text(strip=True)
            else:
                price = "N/A"

            # Estrai la valutazione (rating) del prodotto
            rating = soup.find("span", {"class": "a-icon-alt"})
            if rating:
                rating = rating.get_text(strip=True)
            else:
                rating = "N/A"

            # Estrai il numero di recensioni
            reviews = soup.find("span", {"id": "acrCustomerReviewText"})
            if reviews:
                reviews = reviews.get_text(strip=True)
            else:
                reviews = "N/A"

            # Stampa i risultati
            print(f"Title: {title}")
            print(f"Price: {price}")
            print(f"Rating: {rating}")
            print(f"Reviews: {reviews}")

    else:
        print(
            f"Errore: Impossibile accedere alla pagina, status code: {response.status_code}"
        )


scraper(urlAmazon)
