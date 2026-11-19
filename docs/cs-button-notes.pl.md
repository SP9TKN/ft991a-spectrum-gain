# Przycisk C.S w FT-991A: obsługa w MAIN

Notatki z analizy, stan 02.11.2026, MAIN V02-07, plik `analiza/main/main_v0207.bin`.
Analiza statyczna, tylko odczyt, bez sprawdzenia na radiu. Nic nie zbudowano ani nie zmieniono.

Odczyt kodu: `tools/h8sx_dis.py`. Dekoder nie rozumie prefiksu `6a 30/38 <adres32>` (btst/bset/bclr na adresie)
ani `01 7d`, więc te rozkazy trzeba składać ręcznie.

## Od klawisza do zdarzenia

1. Skan matrycy `0x15444`: 4 rzędy (maska 1/2/4/8 na 0xFFFF5C), odczyt z 0xFFFF4D. Bufor 6 bajtów trafia do 0xFF2450, gdy dwa kolejne pełne skany są takie same.
2. Porównanie `0x15506`: 24 bajty 0xFF2450 (24×8 = 192 kody) z poprzednim stanem 0xFF2437. Flagi w 0xFF2009:
   - bit 3: zmiana
   - bit 2: wszystko puszczone
   - bit 1: więcej niż jeden klawisz
   - bit 0: zdarzenie obsłużone, kolejne zdarzenia tego naciśnięcia są blokowane
   - kod klawisza trafia do 0xFF2433
3. Kody od 0x30 to dotyk z TFT (0xFF25E8, kod + 0x30, `0x15614`). Kody 0x20–0x2B to drabinka ADC, 12 poziomów (`0x15656`, `0x156D6`).
4. Automat `0x152C2`, stan w 0xFF2431 (0 spoczynek, 1 jeden klawisz trzymany, 2 czekanie na puszczenie wszystkiego).

C.S ma kod **0x11** (bajt 2, bit 1, czyli rząd z maską 0x04).

## Sześć tabel zdarzeń

Każda ma 192 wpisy po 4 bajty, indeks to 0xFF2432. `0x15442` to samo `rts`.

| Tabela | Baza | Kiedy się wykonuje | Wpis C.S | Adres wpisu |
|---|---|---|---|---|
| T0 | 0x1572A | naciśnięcie, od razu | **0xB0C2** | 0x1576E |
| T1 | 0x15A36 | puszczenie przed upływem czasu długiego | pusty | 0x15A7A |
| T2 | 0x15D42 | długie, raz, gdy licznik dojdzie do 0 | pusty | 0x15D86 |
| T3 | 0x1604E | dalej trzymany, co takt po T2 | pusty | 0x16092 |
| T4 | 0x1635A | dołożony drugi klawisz, stan przechodzi na 2 | pusty | 0x1639E |
| T5 | 0x16666 | każde puszczenie | pusty | 0x166AA |

T1, T2, T3 i T5 nie wykonują się przy ustawionym 0xFF2009 bit 0. Naciśnięcie ten bit kasuje (`0x15358`).

Czas długiego naciśnięcia: licznik 0xFF2434 = 200 (`0x1531E`), zmniejszany co 5 jednostek taktu (0xFF2007 bit 1, `0x323FE`).
Przy 1 ms na jednostkę daje to ok. 1 s. Ta jednostka to wniosek z kodu, sprzętowego timera nie sprawdzałem.
Takty w 0xFF2007: bit 3 co 1 jednostkę, bit 2 co 2, bit 1 co 5, bit 0 co 10.

Przy starcie radia automat dostaje stan 2 (`0x1374`), więc klawisz trzymany przy włączaniu nie daje zdarzenia aż do puszczenia.

## Procedura C.S, 0xB0C2

Działa już przy naciśnięciu. Puszczenie i przytrzymanie C.S nie robią nic.

1. Blokady. Każda prowadzi do `0xB1AC`: ustawia 0xFF2009 bit 0 i kończy.
   - 0xFF2048.7, ustawiany przy starcie w `0x14D8`
   - `0x35BDE`: 0xFF200B.7, 0xFF2011.4, 0xFF2011.3
   - 0xFF204E.5
   - 0xFF201D.7, ustawiany przy starcie w `0x150E`, kasowany na ścieżce zapisu kalibracji `0xA81A`/`0xA826`; najpewniej tryb serwisowy
   - 0xFF201D.2
   - 0xFFB315.6 i .5, przełączane innymi klawiszami (`0xB08E`, `0xB74C`)
   - 0xFF201E.6 i .7
   - 0xFF205A.7, 0xFF205F.7, 0xFF2064.7, 0xFF2065.7, 0xFF2066.7

   Znaczenie większości tych flag jest nieustalone.
2. 0xFF2020.7 ustawiony: `jsr 0x2BDF8` kasuje ten stan, potem wyjście przez `0xB1AC`. C.S zamyka wtedy tę nakładkę i nie robi nic więcej.
3. `jsr 0x11432` (kasuje 0xFF201E.0) i `jsr 0x3089A` (przy 0xFF2014.6 przywraca 0xFFB471 z 0xFF23F6 i kończy stan czasowy).
4. Rozgałęzienie na 0xFF201D.6, czyli menu otwarte (`0xA7AC` ten bit ustawia):
   - **Menu otwarte, `0xB178`:** 0xFFB319 = 0xFFB316 (bieżąca pozycja menu), zapis do FRAM przez `0x8550` (r1 = 0x012D, er3 = 0xFFB318). Menu zostaje otwarte.
   - **Poza menu, `0xB18A`:** 0xFFB316 = 0xFFB319, 0xFFB317 = 0 (wniosek z kontekstu: `01 7d 48 00 <adres>` działa jak zerowanie), `jsr 0xA7AC` otwiera menu na tej pozycji.
5. `jsr 0x48F6` (`0xB1A2`), koniec.

Przypisanie pozycji do C.S działa więc tak: w menu przypisuje, poza menu otwiera. Limitu indeksu w kodzie nie ma.

## Wpływ na test_06 i test_07

- Oba podmieniają tylko gałąź poza menu (`0xB18A`). Przypisanie w menu zostaje bez zmian, ale nie da się już otworzyć menu przez C.S.
- Blokady z punktu 1 i skutki uboczne z punktu 3 nadal działają, także gdy C.S przełącza gain. Gdy blokada jest aktywna, C.S nic nie przełącza. Który ekran którą blokadę ustawia, nie sprawdzałem.

## Warianty możliwe bez TFT (niezbudowane, użytkownik nie zdecydował)

**Trzymanie C.S + MULTI = gain.** Stan trzymania jest już w RAM: 0xFF2431 == 1 i 0xFF2432 == 0x11.
- Kod obrotu sprawdza ten warunek w miejscu haka `0x1405E` z test_07.
- Po obrocie ustawia 0xFF2009 bit 0, żeby puszczenie nie wywołało zwykłej akcji C.S.
- Sam hak nie wystarczy, bo T0 otwiera menu już przy naciśnięciu. Trzeba przenieść wpis: T0[0x11] -> `0x15442`, T1[0x11] -> `0xB0C2`. Menu otworzy się wtedy przy puszczeniu.

**Krótkie i długie C.S.** Po tym samym przeniesieniu T2[0x11] (`0x15D86`) wskazuje nową funkcję uruchamianą po ok. 1 s.
Puszczenie po czasie długim nie wykona T1, bo licznik jest już 0.

Do sprawdzenia przed budową:
- działanie tej samej ścieżki z obrotem przy zapisie 0x9594 w czasie trzymania
- czy MULTI pracuje w trakcie trzymania klawisza (pętla główna nie powinna tego blokować, nie sprawdzone)
- adresy tabel w obrazie test_03/test_07 (powinny być te same, bo builder dokleja kod za końcem i `b.patch` sprawdza oczekiwane bajty, ale tego nie porównywałem)

## Zasady użytkownika

- Nic nie wgrywać do radia. Wgrywa sam użytkownik, tylko po wyraźnej decyzji.
- Bez commitów.
- Odblokowania TX nie analizować ani nie dobudowywać. TXW nie ruszać.
- Tylko pliki FT-991A, nie FT-991.
- Odrzucone, nie proponować: automat poziomu szumu, uśrednianie waterfalla, test_05, presety w menu 118.

Reszta historii: pamięć `project_ft991a_firmware.md`.
