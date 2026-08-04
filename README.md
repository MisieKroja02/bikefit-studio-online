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


## Zmiana v3.6

- Panel „Import geometrii z linku” jest domyślnie zwinięty i rozwija się dopiero po kliknięciu użytkownika.


## Usuwanie błędnych geometrii — v3.8

Własne geometrie można usunąć bezpośrednio pod listą wyboru. Wbudowane geometrie przykładowe są chronione. Po rozwinięciu sekcji „Usuń wybraną geometrię” należy zaznaczyć potwierdzenie i kliknąć przycisk usuwania. Operacja usuwa rekord zarówno z trwałego folderu online, jak i z lokalnej kopii.

## v4.3
- Naprawiono konflikt kluczy Streamlit w panelu komponentów.
- Rozdzielono parametry geometrii ramy i wymiennych komponentów.

## v4.4

- wyraźna regulacja wysokości podkładek pod mostkiem,
- rozwinięty panel wymiennych komponentów,
- bezpieczne callbacki do doboru i optymalizacji ustawienia.
