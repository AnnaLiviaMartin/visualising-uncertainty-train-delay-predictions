# README – Umfrage-Auswertung 

Dieses Tool macht die Auswertung für Likert-Fragen möglichst geradlinig:

1. **Rohdaten-CSV** einlesen (Antworttexte wie „Teils/teils“, „Stimmt eher zu“…).
2. **Mapping-CSV** einlesen (Text → Zahlencode).
3. **Include-CSV** einlesen (welche Frage-Nummern ausgewertet werden sollen).
4. Aus den **kodierten Zahlen** werden Kennwerte und ein einfacher Signifikanztest berechnet.

---

## Welche Dateien werden gebraucht?

### 1) Rohdaten (`raw.csv`)
- Spalten heißen in der Regel so:  
  `Frage <nummer> - <Fragetext>`
- Zellen enthalten Antworttexte oder manchmal schon Zahlen.

### 2) Mapping (`mapping.csv`)
Mindestens zwei Spalten:
- `value` (oder ähnlich): Antworttext
- `code` (oder ähnlich): Zahlencode

Beispiel:

| value | code |
|---|---:|
| Stimmt überhaupt nicht zu | 1 |
| Stimmt eher nicht zu | 2 |
| Teils/teils | 3 |
| Stimmt eher zu | 4 |
| Stimmt voll und ganz zu | 5 |

Wichtig:
- Textvergleich ist **case-insensitive** (Groß/Klein egal).
- Wenn ein `value` fehlt oder `code` leer ist, wird die Zelle **NaN** (nicht auswertbar), bis das Mapping ergänzt ist.

### 3) Include-Liste (`include_questions.csv`)
Eine Spalte mit Frage-Nummern, z. B.:

```
question_number
4
6
7
...
```

Nur diese Fragen werden verarbeitet (alles andere wird ignoriert). Sinnvoll ist hier: **nur Fragen, die wirklich Likert-Skalen-Antworten haben**. Freitext oder kategoriale Fragen bringen für diesen Signifikanztest nichts.

---

## Was kommt raus?

### `codeddata_included.csv`
Rohdaten, aber überall Zahlen:
- leere Zelle → NaN
- numerischer Text (z. B. „3“) → 3
- Antworttext → Mapping-Code
- unbekannter Antworttext → NaN

### `descriptives_included.csv`
Pro Spalte (Frage) Kennwerte:
- `n` (wie viele gültige Werte)
- `mean` (Durchschnitt)
- `median` (Median)
- `std` (Standardabweichung, Stichprobe)
- `min`, `max`

### `likert_stats_included.csv`
Zusätzlich (nur für als Likert erkannte Spalten):
- `c1..c5`: Häufigkeiten der Codes 1..5 (bei 3-stufig entsprechend)
- `k_above`, `k_below`, `ties`, `m_no_ties`
- `p_value` + `significant`

---

## Wie wird „Signifikanz“ hier verstanden?

Es gibt keinen Vergleich zwischen zwei Prototypen oder Gruppen.  
Signifikanz bedeutet hier:

> Weicht die Bewertung systematisch vom neutralen Mittelpunkt ab?

- Bei 1–5 Skalen ist der Mittelpunkt **3**  
- Bei 1–3 Skalen ist der Mittelpunkt **2**

Als Test wird ein **zweiseitiger Sign-Test** genutzt, hier eine gute Ressource dazu https://statistikguru.de/spss/wilcoxon-vorzeichen-rang-test/voraussetzungen-19.html

---

## Sign-Test – kurz erklärt

Die Idee: Antworten werden in drei Kategorien gepackt:

- **unterhalb** des Mittelpunkts  
- **genau** am Mittelpunkt (**ties**)  
- **oberhalb** des Mittelpunkts  

Ties werden für den Test ignoriert, weil sie „weder noch“ sind und die Frage hier ist:  
**geht es eher nach oben oder eher nach unten weg vom neutralen Punkt?**

Dann wird geprüft, ob „oberhalb“ und „unterhalb“ ungefähr 50/50 sind (Nullhypothese).

---

## Allgemeines zur Berechnung


### Was bedeutet was

- `P(...)`    =>  „Wahrscheinlichkeit von …“
- `X`         => Zufalsvariable, Anzahl der Antworten, die auf der „selteneren Seite“ liegen (also entweder unterhalb oder oberhalb des Mittelpunkts)
- m => Anzahl Antworten ohne ties (`m_no_ties`)
- p = 0,5 => Wahrscheinlichkeit für „oberhalb“; genauso 0,5 für „unterhalb“
- „X ~ Binomial(m, 0.5)“      => X verhält sich wie ein Ergebnis aus m Münzwürfen mit Trefferwahrscheinlichkeit 0,5.

### Was ist der p-Wert (`p_value`)?
Der p-Wert ist:

> Wie wahrscheinlich wäre ein Ergebnis *mindestens so extrem wie das beobachtete*,  
> wenn es eigentlich keinen echten Trend gibt (Nullhypothese)?

Klein = „Das wäre unter Zufall eher selten“  
Groß = „Das kann gut durch Zufall passieren“
> FÜr die wissenschaftliche Auswertung wollen wir einen kleinen p-value. Immerhin wollen wir zeigen, dass unsere Ergebnisse Korrelationen/Gründe abbilden und nicht reiner Zufall sind.

### Warum ist das „zweiseitig“?
„Zweiseitig“ heißt: Es ist egal, ob die Abweichung nach oben oder nach unten geht, beides ist „auffällig“.  
Darum wird am Ende mal 2 gerechnet.

---

## Beispielrechnung mit echten Daten aus `likert_stats_included.csv`

Beispielzeile:

- **Frage 20 - Bitte bewerten Sie die folgenden Punkte. - Ich halte diese Vorhersage für glaubwürdig. / (Spalten 1-5)**
- Skala: **1–5**, Mittelpunkt: **3**
- n = **14**
- mean = **1.785714**
- median = **2.0**
- std = **0.425815**
- Häufigkeiten:  
  c1=3, c2=11, c3=0, c4=0, c5=0

### Schritt 1: in „below / ties / above“ umrechnen (bei 1–5)
Bei 1–5 ist „neutral“ die 3.
- below = c1 + c2 = 3 + 11 = **14**
- ties  = c3 = **0**
- above = c4 + c5 = 0 + 0 = **0**

### Schritt 2: Ties entfernen
- m_no_ties = above + below = 0 + 14 = **14**

Das ist die Anzahl Antworten, die wirklich „eine Richtung“ haben (nicht neutral).

### Schritt 3: Sign-Test rechnen
- Es gibt m_no_ties = 14 Antworten ohne ties.
- Unter der Nullhypothese wäre „oben“ und „unten“ 50/50.  
  Also wäre es nicht ungewöhnlich, wenn z. B. 7 oben und 7 unten sind.
- Beobachtet wurde aber: 0 oben und 14 unten. Das ist extrem einseitig.

So wird der p-Wert berechnet:
1. Man nimmt die kleinere Seite: `k = min(above, below)`  
   -> k = min(0, 14) = **0**
2. Man fragt: Wie wahrscheinlich ist es bei 14 „Münzwürfen“ (50/50), dass die kleinere Seite so klein ist wie 0?
   - `P(X <= 0)` bedeutet hier: „Wahrscheinlichkeit, dass X genau 0 ist“
3. Bei fairer Münze ist:
   - Wahrscheinlichkeit für „14 mal gleiche Richtung“ = (0.5)^14
4. zweiseitig wird verdoppelt:
   - p = 2 * (0.5)^14  
   - p = 0.0001220703

Das entspricht dem p-Wert in der Datei:
- p_value = **0.0001220703**

### Schritt 4: Interpretation mit Alpha (α)

> α ist eine vorher festgelegte Grenze, ab wann etwas als „statistisch auffällig“ gilt.  
Der Standardwert ist oft **0.05**, weil das historisch/konventionell in vielen Feldern so genutzt wird.

**Was bedeutet α = 0.05 praktisch?**  
Wenn die Nullhypothese stimmt (kein echter Effekt), dann akzeptiert man bei α=0.05, dass man in etwa **5% der Fälle** trotzdem „signifikant“ sagt (Fehlalarm/False Positive).

In diesem Beispiel:
- p_value = 0.000122… ist viel kleiner als 0.05  
  → Ergebnis ist **signifikant**.

Inhaltlich heißt das:
- Antworten liegen **sehr deutlich unter dem Mittelpunkt (3)**  
  (weil fast alles bei 1–2 ist).  
- Das spricht eher gegen „glaubwürdig“ (je nachdem, wie die Skala gepolt ist).

---

## Wie sollte das im Text interpretiert werden?

- **Median** ist bei Likert oft die wichtigste Zahl („wo liegt die Mitte?“).
- **mean** kann man zusätzlich berichten, aber er ist empfindlicher.
- **std** zeigt, wie stark sich Antworten streuen.
- **p_value** beantwortet nur: „Abweichung vom Mittelpunkt ist auffällig oder nicht also weicht es GENUG vom Mittelpunkt ab?“

>Wichtig:
„Nicht signifikant“ heißt bei kleinen Stichproben oft nur: **zu wenig Daten / zu wenig Power**.

---

## Starten

```bash
pip install -r requirements.txt
streamlit run main.py
```
