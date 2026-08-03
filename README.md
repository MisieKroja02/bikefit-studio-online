# BikeFit Studio Online v3.3

Internetowy konfigurator ustawienia pozycji na rowerze.

## Nowości v3.3

- ocena, czy wybrana rama jest odpowiednia dla rowerzysty,
- wykrywanie ramy prawdopodobnie za małej lub za dużej,
- sugestia porównania sąsiedniego rozmiaru,
- analiza wymaganych korekt stacku i reachu,
- kopia bezpieczeństwa dodanych geometrii,
- przywracanie bazy geometrii z pliku JSON,
- ostrzeżenie o nietrwałym trybie lokalnym.

## Trwałość geometrii

Zmiany zapisane tylko na lokalnym systemie plików Streamlit mogą zniknąć po ponownym wdrożeniu. Trwała wspólna baza wymaga konfiguracji opisanej w `KONFIGURACJA_WSPOLNEJ_BAZY.txt`.

Bez tej konfiguracji przed aktualizacją pobierz kopię geometrii w zakładce `Geometria roweru`.

## Uruchomienie lokalne

```bash
pip install -r requirements.txt
streamlit run app.py
```

Autor: MisieK
