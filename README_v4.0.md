# BikeFit Studio Online v4.0

Kompletna aplikacja Streamlit do doboru pozycji, analizy kątów, ciśnienia opon, oceny rozmiaru ramy i przenoszenia ustawień na realny rower.

## Nowość: interaktywne pomiary

Zakładka **📏 Pomiary roweru** pozwala:

- kliknąć dwa charakterystyczne punkty na modelu,
- automatycznie obliczyć odległość prostą,
- zobaczyć składową poziomą i pionową,
- odczytać kąt odcinka,
- użyć gotowych pomiarów:
  - wysokość siodła,
  - setback S75,
  - S75 → chwyt,
  - drop siodło–chwyt,
  - reach siodło–chwyt,
  - długość mostka,
  - rozstaw osi,
  - długość korby,
  - BB drop,
  - front-center,
- przeczytać instrukcję, jak wykonać dany pomiar zwykłą metrówką.

## Uruchomienie lokalne

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Publikacja

Wgraj całą zawartość katalogu do repozytorium GitHub i wdroż `app.py` w Streamlit Community Cloud.

## Testy

```bash
python -m pytest -q
```

Aktualny wynik: **45/45 testów silnika**.
