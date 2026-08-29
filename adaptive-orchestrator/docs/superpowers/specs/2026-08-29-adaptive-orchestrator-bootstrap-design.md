# Adaptive Orchestrator: bootstrap, preflight i panel

## Cel

Wywołanie `/adaptive-orchestrator` ma utworzyć albo wznowić projekt oparty na `.agent-board/`. Tablica JSON jest jedynym źródłem prawdy. Panel jest niezależną, tylko do odczytu prezentacją bieżących danych.

## Wejścia

### Nowy projekt

1. Jeżeli `.agent-board/` nie istnieje, najpierw zapytaj: „Co budujemy?”.
2. Następnie przeprowadź adaptacyjny preflight: pytaj tylko o informacje potrzebne do zaplanowania projektu i potwierdź wyłącznie zweryfikowane możliwości obecnego harnessu.
3. Zainicjalizuj tablicę, zapisz preflight, zaplanuj pracę i zapewnij panel.

### Wznowienie

1. Jeżeli `.agent-board/` istnieje, nie pytaj ponownie o cel.
2. Zweryfikuj tablicę i odczytaj projekt, zadania, stany, claimy, runy, review i decyzje.
3. Zwięźle zgłoś, co zostało zrobione, co jest zablokowane i jaką pracę można wykonać w bieżącym harnessie.
4. Zapewnij panel, jeżeli brakuje jego plików, a następnie kontynuuj zgodnie z polityką nadzoru.

## Preflight

Preflight zapisuje `environment/<runtime-id>.json`. Nieweryfikowalne dane mają wartość `unknown` i nie mogą spełniać twardych wymagań zadania.

Zawiera on możliwości i modele aktualnego harnessu oraz politykę nadzoru:

- `autopilot`: samodzielne wykonanie poza prawdziwymi blokadami wymagającymi człowieka;
- `ask` + `CEO`: pytania o strategię, zakres, ryzyko i wydanie;
- `ask` + `manager`: dodatkowo istotne kompromisy implementacyjne i integracyjne;
- `ask` + `full_control`: również drobne decyzje wykonawcze.

Preflight pyta też, czy projekt jest multi-harness. Domyślnie jest single-harness, a zadania rozdziela się między modele zweryfikowane w tym harnessie. Przy multi-harness preflight zapisuje znane harnessy, ich możliwości, cele/preferowane role i ewentualną strategię rozkładu obciążenia.

## Planowanie, dopasowanie i przejmowanie pracy

Kontrakt zadania zawiera przenośne twarde wymagania oraz opcjonalną preferencję harnessu. Harness nie jest właścicielem zadania.

Polecenie „znajdź pracę” działa tak:

1. wybiera gotowe zadanie, dla którego bieżący harness spełnia twarde wymagania i jest preferowany;
2. gdy nie ma takiego zadania, znajduje kwalifikujące się zadania z puli innego harnessu i przedstawia propozycję przejęcia z uzasadnieniem;
3. przejęcie wymaga wyraźnej akceptacji użytkownika, nawet w trybie autopilota;
4. aktywny claim innego wykonawcy blokuje przejęcie; wygasły lub sporny claim jest zgłaszany do rozstrzygnięcia.

Faktyczny wykonawca jest zapisywany w claimie i runie; preferencja nie może nadpisać wymagań ani dowodów wykonania.

## Panel

Panel składa się z `.agent-board/dashboard/index.html` i `.agent-board/dashboard/app.js`. Pliki są generowane, jeśli ich brakuje. Nie zawierają migawki ani logiki zapisu.

`serve_dashboard.py` uruchamia lokalny, tylko do odczytu serwer HTTP. Endpoint `/api/board` przy każdym żądaniu czyta aktualne JSON-y i zwraca widok danych potrzebny panelowi. JavaScript odświeża go okresowo i pokazuje projekt, stany zadań, claimy, runy, review oraz błędy odczytu. Otwarcie przez HTTP eliminuje ograniczenia `file://`.

Panel nigdy nie modyfikuje `.agent-board/`; JSON-y pozostają autonomiczne i używalne bez panelu.

## Obsługa błędów

- Nieprawidłowe lub brakujące JSON-y są sygnalizowane w panelu i podczas audytu bez automatycznej naprawy danych.
- Brak panelu powoduje jego ponowne utworzenie; nie powoduje ponownej inicjalizacji tablicy.
- Brak dopasowanej pracy powoduje raport z powodami i wskazaniem następnej sensownej czynności.

## Weryfikacja implementacji

Testy obejmą: inicjalizację nowego projektu, wznowienie, wszystkie poziomy nadzoru, single- i multi-harness, filtrowanie wymagań, propozycję przejęcia wymagającą zgody, odtworzenie panelu oraz odświeżanie API po zmianie JSON-ów.
