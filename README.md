# BikeFit Studio Online v2.4

Internetowy konfigurator pozycji na rowerze. Autor: **MisieK**.

## Funkcje

- wejście przez imię lub pseudonim,
- niezależna sesja dla każdej osoby korzystającej z linku,
- wybór, import i ręczna edycja geometrii roweru,
- dobór ustawienia bazowego,
- optymalizacja pozycji,
- animacja korby według kadencji,
- kąty kolana, biodra, łokcia i tułowia,
- czytelne wymiary M1–M5,
- kalkulator ciśnienia opon,
- raport oraz pobieranie profilu JSON.

## Ważne

Dane nie są zapisywane na GitHubie ani na stałe na serwerze. Każdy użytkownik pracuje w niezależnej sesji swojej przeglądarki. Profil można pobrać jako JSON w zakładce raportu.

## Aktualizacja Streamlit

Podmień `app.py` w głównym katalogu repozytorium, wykonaj commit i w razie potrzeby uruchom `Manage app → Reboot app`.


## Poprawka v2.4

Usunięto modyfikowanie aktywnego `st.session_state` przez `sanitize_numeric_state()` po utworzeniu widżetów. Sanitizacja działa teraz tylko na początku przebiegu aplikacji.


## Nowości v2.4

- płynna animacja wykonywana po stronie przeglądarki,
- właściwy kierunek obrotu korby,
- osobna dostępna zakładka Wykresy kątów,
- bezpieczny przycisk sugerowanego rozkładu masy,
- tryb viewer dla paska Streamlit,
- czysty link do udostępniania: `https://bikefitstudio.streamlit.app/?embed=true&embed_options=dark_theme&embed_options=hide_loading_screen`.


## Zmiany v2.7

Sterowanie animacją zostało przeniesione bezpośrednio pod rysunek roweru. Obejmuje kadencję, pozycję korby, Play/Pauza/Reset, prędkość animacji, skalę oraz przełączniki kątów i wymiarów M1–M5.


## Zmiany v2.7

- ciemne tło wszystkich przycisków,
- jasny tekst na przyciskach,
- poprawione stany aktywne i nieaktywne.
