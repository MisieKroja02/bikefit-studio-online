# BikeFit Studio Online v1.4

Internetowa wersja programu BikeFit Studio przygotowana do uruchomienia w przeglądarce i publikacji na Streamlit Community Cloud.

**Autor: MisieK**

## Funkcje

- wybór roweru z zapisanej bazy,
- edycja całej geometrii,
- import geometrii z adresu internetowego,
- konfigurator rowerzysty: wzrost, przekrok, masa i mobilność,
- dobór ustawienia bazowego,
- automatyczna optymalizacja pozycji,
- symulacja położenia rowerzysty dla wybranego kąta korby,
- czytelne pomiary M1–M5,
- punkt referencyjny siodła S75,
- kalkulator ciśnienia opon,
- zapis i odczyt profilu JSON,
- pobieranie raportu HTML,
- interfejs działający na komputerze, telefonie i tablecie.

## Uruchomienie lokalne

### Windows

Kliknij:

```text
start_local.bat
```

Skrypt doinstaluje Streamlit i otworzy aplikację w przeglądarce.

### Linux / macOS

```bash
./start_local.sh
```

Alternatywnie:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Darmowa publikacja na Streamlit Community Cloud

1. Załóż bezpłatne konto GitHub.
2. Utwórz nowe publiczne repozytorium, np. `bikefit-studio-online`.
3. Wgraj **całą zawartość tego folderu** do katalogu głównego repozytorium.
4. Zaloguj się do Streamlit Community Cloud kontem GitHub.
5. Wybierz `Create app` / `Deploy an app`.
6. Wskaż repozytorium i gałąź `main`.
7. Jako plik startowy wybierz:

```text
app.py
```

8. Naciśnij `Deploy`.

Po wdrożeniu otrzymasz publiczny adres podobny do:

```text
https://bikefit-studio-online.streamlit.app
```

## Struktura projektu

```text
app.py                         główna aplikacja internetowa
requirements.txt              zależności Pythona
.streamlit/config.toml         wygląd i konfiguracja Streamlit
assets/logo_misiek.png         logo programu
bikefit/                       silnik obliczeniowy
  kinematics.py                biomechanika 2D
  optimizer.py                 optymalizator ustawienia
  recommendations.py           konfigurator i pomiary
  tire_pressure.py             dobór ciśnienia
  internet_import.py           import geometrii
  models.py                    modele danych
data/bikes.json                przykładowa baza rowerów
tests/                         testy silnika
```

## Testy

```bash
python -m pytest -q
```

Aktualny silnik przechodzi 6 testów obliczeniowych.

## Ważne ograniczenia

- wyniki stanowią punkt startowy do regulacji,
- pozycję należy zmieniać stopniowo, zwykle po 2–5 mm,
- ból, drętwienie, urazy i wyraźne asymetrie wymagają konsultacji ze specjalistą,
- limity ciśnienia producenta opony i obręczy mają pierwszeństwo przed wynikiem kalkulatora,
- część stron może blokować automatyczny import geometrii; wtedy wartości należy wpisać ręcznie.


## Aktualizacja v1.1

- poprawione białe wartości na białym tle,
- wyraźne ciemne pola tekstowe i liczbowe,
- wybór oraz pełna edycja geometrii bezpośrednio w panelu bocznym,
- możliwość zapisania własnej geometrii w bieżącej sesji,
- czytelniejsze zakładki i podsumowanie geometrii.


## Aktualizacja v1.2

- wymuszony ciemny motyw przez `.streamlit/config.toml`,
- poprawione kolory pól tekstowych, liczbowych, list oraz rozwijanych sekcji,
- import geometrii z linku dostępny bezpośrednio w panelu bocznym,
- szybkie przyciski do Bike Insights, Geometry Geeks i 99 Spokes,
- ręczna edycja geometrii pozostaje w osobnej sekcji.


## Aktualizacja v1.4

- naprawiono białe napisy na białych przyciskach w imporcie geometrii,
- przyciski katalogów rowerowych są renderowane jako stabilne, ciemne przyciski HTML,
- usunięto regułę CSS wymuszającą jasny tekst we wszystkich elementach panelu bocznego,
- zachowano import geometrii z linku oraz ręczną edycję geometrii.


## Zmiany v1.4

- mniejsza i wycentrowana symulacja,
- niższe pole SVG,
- suwak skali symulacji 65–100%, domyślnie 82%.
