# BikeFit Studio Online

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
