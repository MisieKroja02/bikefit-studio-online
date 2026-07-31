# BikeFit Studio Online v1.7

Internetowy konfigurator pozycji na rowerze działający w przeglądarce.

**Autor: MisieK**

## Najważniejsze funkcje

- wybór roweru i pełna edycja geometrii,
- import geometrii z adresu internetowego,
- dobór ustawienia bazowego i automatyczna optymalizacja,
- animacja pedałowania według kadencji,
- Play, Pauza, Reset i regulacja prędkości animacji,
- kąty kolana, biodra, łokcia i tułowia,
- wykres kąta kolana i biodra przez pełny obrót korby,
- czytelne wymiary M1–M5,
- kalkulator ciśnienia opon,
- raport HTML i kopia profilu JSON,
- obsługa wielu użytkowników przez jeden publiczny link,
- zapis każdego profilu jako osobnego pliku JSON w prywatnym repozytorium GitHub.

## Profile użytkowników

Po otwarciu aplikacji użytkownik wpisuje:

- imię lub pseudonim,
- kod profilu o długości co najmniej 4 znaków.

Ten sam pseudonim i kod wczytują poprzednio zapisany profil. Kod nie jest
zapisywany w pliku profilu. Służy do utworzenia osobnego identyfikatora pliku.

Zalecane jest oddzielne, prywatne repozytorium `bikefit-studio-data`.
Szczegółowa instrukcja znajduje się w:

```text
KONFIGURACJA_PROFILI_GITHUB.txt
```

## Publikacja na Streamlit Community Cloud

1. Wgraj zawartość folderu do repozytorium GitHub.
2. W Streamlit Cloud ustaw:
   - Repository: repozytorium aplikacji,
   - Branch: `main`,
   - Main file path: `app.py`.
3. Kliknij Deploy.
4. Skonfiguruj sekrety do zapisu profili.

Przykład sekretów:

```toml
[github]
token = "github_pat_..."
owner = "MisieKroja02"
repo = "bikefit-studio-data"
branch = "main"
folder = "profiles"
```

Prawdziwego tokenu nie wolno umieszczać w publicznym repozytorium.
Dodaje się go w panelu Streamlit Cloud: Manage app → Settings → Secrets.

## Uruchomienie lokalne

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Na Windows można uruchomić `start_local.bat`.

## Testy

```bash
python -m pytest -q
```

Silnik obliczeniowy przechodzi 6 testów.

## Ważne

- aplikacja jest narzędziem orientacyjnym, a nie wyrobem medycznym,
- regulacje na rzeczywistym rowerze należy wykonywać stopniowo,
- ból, drętwienie, urazy i asymetrie wymagają konsultacji ze specjalistą,
- ograniczenia producenta opony i obręczy mają pierwszeństwo przed kalkulatorem.
