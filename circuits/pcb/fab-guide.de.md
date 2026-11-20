# Von Circuit Lab zur JLCPCB-Platine

Unbestückte Platinen mit Durchsteckbauteilen zum Selbstlöten. Die Menünamen entsprechen KiCad 9
und der KiCad-9-Anleitung von JLCPCB. In KiCad 10 sollten sie übereinstimmen; melde verschobene
Menüs. Englische Menünamen stehen zur Orientierung in Klammern.

Du hast drei technische Dateien heruntergeladen: `circuit-lab.net` (Bauteile und Verbindungen),
`circuit-lab-bom.csv` (Stückliste) und `circuit-lab-jlcpcb-rules.txt` (Entwurfsregeln).

## 1. KiCad-Projekt beginnen

- **Raspberry-Pi-Schaltungen:** *Datei → Neues Projekt aus Vorlage (File → New Project from
  Template) → RaspberryPi-HAT*; für eine kleine Platine *RaspberryPi-uHAT*. Enthalten sind der
  offizielle HAT-Umriss, vier M2,5-Befestigungsbohrungen und die 40-polige Buchse `J1` an der
  richtigen Position. Circuit Lab nennt die Pi-Stiftleiste immer `J1`, damit sie dieser Buchse entspricht.
- **Andere Schaltungen:** *Datei → Neues Projekt (File → New Project)*. Zeichne im PCB-Editor den
  Umriss auf **Edge.Cuts**. Ein Rechteck genügt; bis 100 × 100 mm ist die günstigste JLC-Größe.
  Platziere vier Footprints `MountingHole:MountingHole_3.2mm_M3` in den Ecken.

## 2. Entwurfsregeln laden

*Datei → Platinenkonfiguration → Entwurfsregeln → Benutzerdefinierte Regeln
(File → Board Setup → Design Rules → Custom Rules)*: Füge die gesamte Regeldatei ein, klicke
**Regelsyntax prüfen (Check Rule Syntax)** und dann OK. Die Regeln berücksichtigen die normalen
JLCPCB-Grenzen für zwei Lagen mit etwas Reserve.

Stelle unter **Netzklassen (Net Classes)** für die Standardklasse 0,25 mm Leiterbahnbreite und
0,2 mm Abstand ein. Ergänze eine **Power**-Klasse mit 0,5 mm (etwa 1 A bei 1 oz Kupfer) für
Versorgung, Masse und Spulennetze; für mehr als 2 A verwende 1,0 mm.

## 3. Netzliste importieren

PCB-Editor: *Datei → Importieren → Netzliste (File → Import → Netlist…)*; wähle `circuit-lab.net`.

- **Footprints anhand der Referenzbezeichner verknüpfen (Link footprints using: Reference
  designators)**. So bleibt `J1` aus der Vorlage an seinem Platz.
- **Footprints ohne Symbole löschen (Delete footprints with no symbols)** nicht aktivieren;
  sonst verschwinden die Befestigungsbohrungen.
- Klicke **PCB aktualisieren (Update PCB)**. Die Bauteile erscheinen zunächst als Stapel;
  dünne Luftlinien zeigen die erforderlichen Verbindungen.

## 4. Platzieren und routen

1. Ziehe die Bauteile auf die Platine. Setze die Kondensatoren von Reglern und Operationsverstärkern
   direkt an deren Anschlüsse; der Export nennt die benötigten Bauteile. Halte die Schleife aus
   Eingang, Ausgang und Masse des Reglers klein.
2. Route die Leiterbahnen (**X**). Nutze für Versorgung und Spulenströme die Klasse Power.
3. Lege auf der Rückseite eine Massefläche an: *Platzieren → Zone (Place → Zone)* auf **B.Cu**,
   Netz **GND**, um die Platine herum. **B** füllt die Flächen nach Änderungen neu.
4. Ergänze Platinenname und Datum als Text mit mindestens 1,0 mm Höhe.

## 5. Prüfen

- *Prüfen → Entwurfsregelprüfung (Inspect → Design Rules Checker)*: ausführen, bis **0 Fehler**
  angezeigt werden. Lies auch die Warnungen.
- *Ansicht → 3D-Betrachter (View → 3D Viewer)*: Alle Bauteile auf der richtigen Seite, keine Überlappungen.
- **Im Maßstab 1:1 auf Papier drucken** und die echten Bauteilanschlüsse durchstecken. So erkennst
  du vor der Bestellung falsche Footprints oder Anschlussreihenfolgen. Prüfe jedes Bauteil, das im
  Export als Entwurf gekennzeichnet wurde.

## 6. Gerberdateien erzeugen (JLCPCB-Einstellungen für KiCad 9)

*Datei → Plotten (File → Plot)*:

- Lagen: **F.Cu, B.Cu, F.Silkscreen, B.Silkscreen, F.Mask, B.Mask, Edge.Cuts**.
  F.Paste/B.Paste nur für Schablonen oder Bestückung.
- Format **Gerber**; Flächenfüllungen vor dem Plotten prüfen; Bohrmarkierungen **Keine (None)**;
  Maßstab 1:1; gefüllter Plotmodus; **Protel-Dateiendungen verwenden (Use Protel filename
  extensions)**; **Erweitertes X2-Format verwenden (Use extended X2 format)**; **Netzlistenattribute
  einschließen (Include netlist attributes)**; Koordinatenformat **4.6, Einheit mm**.
- Ausgabe in einen Ordner mit einfachem Namen ohne Leerzeichen; dann **Plotten (Plot)**.

Im selben Dialog **Bohrdateien erzeugen (Generate Drill Files…)**: **Excellon**, alternative
Bohrmethode für Langlöcher, Ursprung **Absolut (Absolute)**, Einheit **Millimeter (Millimeters)**,
Nullen **Dezimalformat (Decimal format)**, PTH und NPTH in **getrennten** Dateien, gleicher
Ordner. Klicke **Erzeugen (Generate)**.

## 7. Bestellen

1. Verpacke den Ordner als ZIP: alle `.g*`-Dateien und beide `.drl`-Dateien; englische Dateinamen.
2. Lade das ZIP auf jlcpcb.com hoch. Für eine erste Platine passen die Vorgaben: zwei Lagen,
   1,6 mm FR-4, HASL (auf Wunsch bleifrei), Stückzahl 5.
3. Prüfe im JLC-Gerberbetrachter: geschlossener Umriss, Bohrungen an den erwarteten Positionen,
   lesbare Beschriftung.
4. Bestelle. Die JLC-Bestückung benötigt LCSC-Teilenummern und eine Platzierungsdatei, die Circuit
   Lab noch nicht erzeugt. Löte die Bauteile selbst anhand der Stückliste ein.

## Quellen

- JLCPCB-Fertigungsmöglichkeiten: <https://jlcpcb.com/capabilities/pcb-capabilities> (geprüft 2026-10-22)
- JLCPCB-Anleitung für KiCad-9-Gerberdateien: <https://jlcpcb.com/help/article/how-to-generate-gerber-and-drill-files-in-kicad-9>
- KiCad-Vorlagen: <https://gitlab.com/kicad/libraries/kicad-templates> (RaspberryPi-HAT)
