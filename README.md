# BikeFit Studio Online v3.1

Internetowy konfigurator pozycji na rowerze. Autor: **MisieK**.

## Najważniejsze funkcje

- wejście przez imię lub pseudonim,
- niezależna sesja każdej osoby korzystającej z linku,
- wybór, import i ręczna edycja geometrii roweru,
- wspólna baza geometrii dodanych przez użytkowników,
- dobór ustawienia bazowego i automatyczna optymalizacja,
- płynna animacja korby według kadencji,
- kąty kolana, biodra, łokcia i tułowia,
- czytelne wymiary M1–M5 i regulacja siodła na szynach,
- kalkulator ciśnienia opon,
- wykres kątów przez pełny obrót korby,
- raport HTML oraz kopia profilu JSON,
- licznik odwiedzin w stopce.

## Zmiany v3.1

- neutralne dane startowe: 175 cm, 75 kg, przekrok 810 mm,
- domyślna geometria demonstracyjna Gravel M,
- geometrie importowane i wpisywane ręcznie mogą być zapisywane we wspólnej trwałej bazie,
- zapis wspólnej geometrii jest wykonywany w tle; użytkownik nie widzi odnośników administracyjnych,
- dodano Bike-Stats zamiast 99 Spokes,
- importer rozpoznaje również popularne niemieckie nazwy parametrów,
- licznik przeniesiono na CounterAPI i zabezpieczono przed wielokrotnym naliczaniem przy odświeżaniu,
- awaria wspólnej bazy lub licznika nie zatrzymuje konfiguratora.

## Uruchomienie lokalne

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Wdrożenie

Repozytorium powinno zawierać w katalogu głównym:

- `app.py`,
- `requirements.txt`,
- foldery `bikefit`, `data`, `assets`, `.streamlit`.

W Streamlit Community Cloud jako główny plik wybierz `app.py`.

## Trwała wspólna baza geometrii

Bez konfiguracji aplikacja używa lokalnego pliku `data/community_bikes.json`. Działa on podczas bieżącego uruchomienia serwera, ale hosting może go wyczyścić przy ponownym wdrożeniu.

Aby wszystkie dodane geometrie pozostały po restarcie i były widoczne dla wszystkich osób, skonfiguruj sekcję `[geometry_store]` w Streamlit Secrets. Dokładna instrukcja znajduje się w pliku:

`KONFIGURACJA_WSPOLNEJ_BAZY.txt`

Token nigdy nie powinien znajdować się w repozytorium ani w `app.py`.

## Testy

```bash
python -m pytest -q
```

Pakiet zawiera testy silnika biomechanicznego, importera, kalkulatora opon, wspólnej bazy geometrii, licznika i pełny test uruchomienia interfejsu z atrapą Streamlit.

## Zastrzeżenie

Program jest narzędziem orientacyjnym. Nie zastępuje profesjonalnego bike fittingu, fizjoterapeuty ani diagnostyki medycznej.

## Nowości v3.1

- import geometrii działa dwuetapowo: najpierw pobranie danych, potem sprawdzenie i zapis,
- przed zapisaniem można wpisać własną nazwę geometrii,
- nazwa pojawia się na wspólnej liście rowerów zamiast tytułu strony lub adresu URL,
- zapis pod istniejącą nazwą aktualizuje daną geometrię, a nowa nazwa tworzy nową pozycję.
