# BikeFit Studio Online v2.1

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


## Poprawka v2.1

Usunięto modyfikowanie aktywnego `st.session_state` przez `sanitize_numeric_state()` po utworzeniu widżetów. Sanitizacja działa teraz tylko na początku przebiegu aplikacji.
