# Japan 2027 letovi – samostalni tracker

Ovaj sajt radi bez Claude-a. Sve je na tvojim nalozima: GitHub (sajt i dnevna provera), SerpApi (cene sa Google Flights) i Travelpayouts (cene sa Aviasales).

## Šta dobijaš

- Sajt na adresi `https://TVOJE-IME.github.io/IME-REPOA/`.
- Svakog jutra se proverava 8 termina (polazak 10.04–15.05.2027, boravak 15, 18 ili 21 dan, 6 putnika) iz Beograda i Budimpešte za Tokio i Osaku. Ceo prozor se obiđe za oko 2 nedelje, pa ispočetka.
- Dva izvora cena: **Google Flights** (tačan termin, cena za 6 putnika) i **Aviasales** (najjeftinije karte koje su drugi korisnici našli u poslednjih nekoliko dana, ceo prozor odjednom, cena za 1 putnika). Može i samo jedan od njih.
- Kod svake karte su i linkovi **Uporedi: Skyscanner · Kayak · Momondo** sa istim datumima i 6 putnika.
- Kod svake cene je dugme **Otvori kartu**. Ono otvara Google Flights sa tim datumima i 6 putnika, a nađeni let je među prvima.
- Upozorenje kad neka karta padne na €750 po osobi ili ispod: mejl (preko GitHub-a) i, ako želiš, push na telefon.

## Podešavanje (oko 15 minuta, jednom)

1. **Nov mejl (preporuka).** Ako hoćeš potpunu odvojenost, otvori nov Gmail koji samo ti koristiš.
2. **GitHub nalog.** Registruj se na https://github.com/signup sa tim mejlom.
3. **SerpApi ključ.** Registruj se na https://serpapi.com (besplatno, 250 pretraga mesečno, kartica nije potrebna). Kopiraj „Your Private API Key“ sa https://serpapi.com/manage-api-key.
3b. **Travelpayouts token (Aviasales).** Registruj se na https://www.travelpayouts.com (besplatno). Posle prijave otvori profil, odeljak **API token**, i kopiraj token. Ako traži „projekat“ ili sajt, upiši adresu svog budućeg GitHub sajta.
4. **Nov repo.** Na GitHub-u klikni **New repository**, daj mu neupadljivo ime (npr. `putovanje-27`), izaberi **Public** (besplatan GitHub Pages radi samo za javne repoe; ključ ostaje tajan) i klikni **Create**.
5. **Postavi fajlove.** Na stranici repoa klikni **uploading an existing file**. Raspakuj zip i prevuci SVE iz foldera `japan-letovi`, uključujući skriveni folder `.github`. Na Mac-u ga prikazuješ sa Cmd+Shift+. a na Windows-u sa View → Hidden items. Klikni **Commit changes**.
   - Ako se `.github` ne prenese, klikni **Add file → Create new file**, upiši ime `.github/workflows/check.yml` i nalepi sadržaj tog fajla.
6. **Tajni ključevi.** Idi na **Settings → Secrets and variables → Actions → New repository secret** i dodaj:
   - `SERPAPI_KEY`: ključ sa SerpApi
   - `TRAVELPAYOUTS_TOKEN`: token sa Travelpayouts
   Dovoljan je i samo jedan od njih. Tada radi samo taj izvor.
7. **Uključi sajt.** Idi na **Settings → Pages**, pod Source izaberi **Deploy from a branch**, Branch `main`, folder `/ (root)` i klikni **Save**. Za minut-dva dobijaš adresu sajta.
8. **Prvo pokretanje.** Otvori **Actions → Dnevna provera cena → Run workflow**. Ako pita, prvo klikni „I understand… enable workflows“. Posle oko minut osveži sajt.

## Upozorenja

- **Mejl.** Kad cena padne ispod cilja, otvara se „Issue“ u repou i GitHub ti šalje mejl. Proveri da je uključeno: avatar → Settings → Notifications → Email.
- **Push na telefon (opciono).** Instaliraj aplikaciju **ntfy** (Android/iOS) i pretplati se na neku dugu, nasumičnu temu, npr. `japan-k7x93qpl2`. Zatim dodaj secret `NTFY_TOPIC` sa istom vrednošću. Svako ko zna ime teme može da čita poruke, pa neka bude nasumično.

## Promene

U `scripts/check_prices.py`, na vrhu fajla:

- `FIRST_DEPARTURE` / `LAST_DEPARTURE`: prozor polaska
- `MIN_STAY` / `MAX_STAY`: najkraći i najduži boravak (za Aviasales)
- `STAY_DAYS`: koliko dana boravka se proverava
- `ADULTS`, `TARGET_PER_PERSON`: broj putnika i ciljna cena
- `SEARCHES_PER_RUN`: pretraga po danu (8 × 31 dan = 248, malo ispod besplatnih 250)

## Provera posle prvog pokretanja

Google Flights za više putnika prikazuje ukupnu cenu, pa skripta deli sa 6. Klikni jedno „Otvori kartu“ i uporedi cenu. Ako je cena na sajtu 6 puta manja nego na Google Flights-u, idi na Settings → Secrets and variables → Actions → kartica **Variables** → New repository variable, ime `PRICE_IS_TOTAL`, vrednost `false`.

## Zašto Skyscanner nije poseban izvor

Skyscanner daje pristup ceni samo firmama koje odobri njihov tim za partnerstva, a pojedinci ga ne mogu dobiti. Isto važi za Kiwi. Zato sajt za svaku nađenu kartu pravi direktan link na Skyscanner, Kayak i Momondo sa istim datumima i 6 putnika, pa je poređenje jedan klik.
