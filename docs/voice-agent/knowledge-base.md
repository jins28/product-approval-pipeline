# Wissensdatenbank: Produktdaten-Pipeline mit menschlicher Freigabe

Diese Wissensdatenbank beschreibt ein Portfolio-Projekt. Der Sprachassistent „Pipeline-Guide“ nutzt sie, um Testerinnen und Testern die Automatisierung zu erklären.

---

## 1. Worum geht es? (Kurzfassung)

Das Projekt ist eine Automatisierung für den E-Commerce und das Fulfillment. Sie holt neue Produktdaten von der Website eines Lieferanten, speichert sie in einem Google Sheet, lässt die Texte von einer KI ins Deutsche übersetzen und wartet dann auf die Freigabe durch einen Menschen. Erst freigegebene Produkte werden automatisch in einen Onlineshop hochgeladen.

In einem Satz: Neue Lieferantenprodukte landen automatisch und übersetzt im Shop, aber nur, nachdem ein Mensch sie geprüft und freigegeben hat.

## 2. Welches Problem löst das?

Online-Händler und Fulfillment-Dienstleister bekommen ständig neue Produkte von Lieferanten. Normalerweise kopiert jemand Namen, Preise, Maße und Beschreibungen von Hand aus der Lieferanten-Website, übersetzt die Texte und legt die Produkte im Shop an. Das ist langsam, fehleranfällig und langweilig.

Die Automatisierung übernimmt das Sammeln, Prüfen auf Duplikate, Übersetzen und Hochladen. Der Mensch macht nur noch das, was ein Mensch gut kann: entscheiden, ob ein Produkt in den Shop soll. Dieses Prinzip nennt man „Human in the Loop“, also ein Mensch in der Schleife.

## 3. Die Bausteine

- **Lieferanten-Website „Nordholm Furniture Co.“**: eine frei erfundene Möbelfirma mit zehn Produkten, fünf Sofas und fünf Stühlen. Die Texte sind auf Englisch, die Preise in Euro, die Bilder sind einfache Zeichnungen. Sie dient als Datenquelle.
- **Scraper**: ein kleines Python-Programm. Es liest die Lieferanten-Website wie ein Besucher, sammelt pro Produkt Name, Preis, Artikelnummer, Beschreibung, Maße, Material und Verarbeitung, Eigenschaften und Haptik sowie die Bilder.
- **n8n**: ein Werkzeug zur Automatisierung, mit dem Abläufe als Workflows gebaut werden. n8n steuert alle Schritte.
- **Google Sheet „Product Pipeline“**: die Übersichtstabelle. Hier steht jedes Produkt mit seinem Status, und hier gibt ein Mensch die Produkte frei.
- **OpenAI**: eine KI, die die englischen Produkttexte ins Deutsche übersetzt.
- **Demo-Shop („Demo Möbelshop“)**: der Onlineshop des Kunden, also das Ziel. Er hat eine Schnittstelle zum Hochladen von Produkten und eine Website, auf der die Produkte erscheinen. Es ist ein Demo-Shop, Bestellungen sind nicht möglich.
- **Testseite**: die Seite, auf der Sie gerade sind. Von hier aus starten Sie die Automatisierung.

## 4. So testen Sie die Automatisierung (Schritt für Schritt)

**Vorbereitung:** Schauen Sie sich zuerst die beiden Websites an. Auf der Testseite gibt es dafür zwei Links: „Lieferanten-Website“ und „Shop-Website“. So sehen Sie vorher, welche Produkte der Lieferant hat und was schon im Shop ist.

**Schritt 1: „Neue Produkte prüfen“**
- Geben Sie das Demo-Passwort ein und klicken Sie auf „Neue Produkte prüfen“.
- Damit startet der erste Workflow. Er holt Produkte von der Lieferanten-Website, prüft, welche noch nicht im Google Sheet stehen, trägt nur die neuen ein und lässt die Texte übersetzen.
- Das dauert meistens zwischen zehn und dreißig Sekunden.
- Danach stehen die neuen Produkte im Google Sheet mit dem Status „Wartet auf Freigabe“.

**Schritt 2: „Google Sheet öffnen“ und freigeben**
- Klicken Sie auf „Google Sheet öffnen“.
- Jede Zeile ist ein Produkt. Sie sehen die englischen Originaltexte und daneben die deutschen Übersetzungen.
- In der Spalte „approval“ wählen Sie im Auswahlmenü für jedes Produkt „Approved“ für freigeben oder „Not approved“ für ablehnen.
- Ändern Sie bitte nur die Spalte „approval“. Die Spalte „status“ wird von der Automatisierung selbst gepflegt.

**Schritt 3: „Freigegebene Produkte hochladen“**
- Gehen Sie zurück zur Testseite und klicken Sie auf „Freigegebene Produkte hochladen“.
- Damit startet der zweite Workflow. Er lädt alle freigegebenen Produkte in den Shop hoch und setzt den Status auf „Hochgeladen“. Abgelehnte Produkte bekommen den Status „Abgelehnt“.
- Das dauert nur wenige Sekunden.

**Ergebnis ansehen:** Öffnen Sie die Shop-Website. Die freigegebenen Produkte erscheinen dort mit deutscher Beschreibung, Bildern, Maßen, Material und Eigenschaften. Mit einem Klick auf ein Produkt öffnet sich seine Detailseite.

## 5. Was bedeuten die Status im Google Sheet?

- **Neu**: Das Produkt wurde gerade von der Lieferanten-Website geholt und eingetragen. Die Übersetzung läuft noch.
- **Wartet auf Freigabe**: Die Übersetzung ist fertig. Jetzt muss ein Mensch entscheiden.
- **Hochgeladen**: Das Produkt wurde freigegeben und ist jetzt im Shop.
- **Abgelehnt**: Ein Mensch hat „Not approved“ gewählt. Das Produkt wird nicht hochgeladen.
- **Fehler**: Bei einem Schritt ist etwas schiefgegangen. Der Grund steht in der Spalte „error“. Ein fehlgeschlagener Upload wird beim nächsten Klick auf „Freigegebene Produkte hochladen“ automatisch noch einmal versucht.

Es gibt zwei getrennte Spalten: „approval“ ist die Entscheidung des Menschen, „status“ ist der Stand der Maschine. So kann ein Mensch die Automatisierung nicht versehentlich durcheinanderbringen.

## 6. Was passiert im Hintergrund?

**Workflow 1 „Neue Produkte prüfen“:**
1. Der Button auf der Testseite ruft über die Shop-Server-Seite einen Webhook von n8n auf. Ein Webhook ist eine Internetadresse, die einen Workflow startet, sobald sie aufgerufen wird.
2. n8n bittet den Scraper, Produkte von der Lieferanten-Website zu holen.
3. n8n liest die vorhandenen Zeilen im Google Sheet und vergleicht die Produkt-Links. Produkte, die schon drinstehen, werden übersprungen. Das ist die Duplikatprüfung.
4. Neue Produkte werden mit dem Status „Neu“ eingetragen.
5. Für jedes neue Produkt fragt n8n OpenAI nach einer deutschen Übersetzung von Beschreibung, Maßen, Material und Eigenschaften.
6. Die Übersetzung wird im Sheet gespeichert, der Status wird „Wartet auf Freigabe“. Klappt die Übersetzung nicht, wird der Status „Fehler“ mit dem Grund.
Derselbe Workflow läuft zusätzlich jeden Morgen um sieben Uhr automatisch.

**Workflow 2 „Freigegebene Produkte hochladen“:**
1. n8n liest alle Zeilen im Google Sheet.
2. Zeilen mit „Approved“ und dem Status „Wartet auf Freigabe“ werden an die Schnittstelle des Shops geschickt.
3. Bei Erfolg wird der Status „Hochgeladen“, bei einem Problem „Fehler“ mit dem Grund.
4. Zeilen mit „Not approved“ bekommen den Status „Abgelehnt“.

## 7. Warum wurde es so gebaut? (Technische Entscheidungen)

- **Mensch in der Schleife:** Eine KI-Übersetzung kann Fehler machen, und nicht jedes Lieferantenprodukt passt ins Sortiment. Deshalb entscheidet ein Mensch, bevor etwas öffentlich wird.
- **Google Sheet als Steuerzentrale:** Jeder kennt Tabellen. Fachabteilungen können ohne Schulung prüfen und freigeben.
- **Keine Duplikate:** Der Produkt-Link ist der eindeutige Schlüssel im Sheet. Im Shop ist die Artikelnummer der Schlüssel. Wird ein Produkt zweimal geschickt, aktualisiert der Shop es, statt es doppelt anzulegen. Wiederholungen sind dadurch ungefährlich.
- **Scraper als eigener Dienst:** Der Python-Scraper läuft getrennt und wird von n8n über eine Internetadresse aufgerufen. So lässt er sich einzeln testen und austauschen.
- **Höflicher Scraper:** Er beachtet die Regeln der Website in der Datei robots.txt, macht kleine Pausen zwischen Anfragen und wartet, wenn eine Website „zu viele Anfragen“ meldet.
- **Sicherheit:** Passwörter und Schlüssel stehen nie im Programmcode, sondern in geschützten Einstellungen. Die Buttons der Testseite sind mit einem Demo-Passwort geschützt und haben eine Wartezeit von 60 Sekunden, damit niemand die Automatisierung ständig startet. n8n selbst ist nicht öffentlich erreichbar, nur der Shop leitet die Klicks weiter.
- **Fehlerbehandlung:** Scheitert ein Produkt, bekommt nur dieses Produkt den Status „Fehler“ mit dem Grund. Die anderen Produkte laufen normal weiter.

## 8. Eingesetzte Technik

n8n für die Workflows, Python mit FastAPI für den Scraper und den Demo-Shop, Google Sheets als Freigabe-Oberfläche, die OpenAI-Schnittstelle für die Übersetzung, Docker, damit alle Teile mit einem Befehl starten, und ElevenLabs für diesen Sprachassistenten. Der Shop nutzt ein ähnliches Datenformat wie Shopify, damit ein späterer Wechsel zu einem echten Shop einfach ist.

## 9. Häufige Fragen

**Ist das ein echter Shop, ein echter Lieferant?**
Nein. „Nordholm Furniture Co.“ und alle Produkte sind frei erfunden, die Bilder sind Zeichnungen. Der Shop ist ein Demo-Shop ohne Bestellungen. Die Automatisierung selbst arbeitet aber genauso wie in einem echten Einsatz.

**Warum sehe ich nach Schritt 1 keine neuen Produkte?**
Wahrscheinlich stehen alle Produkte des Lieferanten schon im Sheet. Die Duplikatprüfung trägt jedes Produkt nur einmal ein. Das ist gewollt. Der Entwickler kann das Sheet für eine neue Vorführung leeren.

**Wie lange dauert ein Durchlauf?**
Schritt 1 dauert meist zehn bis dreißig Sekunden, Schritt 3 nur wenige Sekunden.

**Warum muss ich warten, bevor ich einen Button noch einmal drücken kann?**
Jeder Button hat eine Wartezeit von 60 Sekunden. Das schützt vor versehentlichem Mehrfachklicken und begrenzt die Kosten für die KI-Übersetzung.

**Was kostet die Übersetzung?**
Pro Produkt nur einen Bruchteil eines Cents.

**Kann ich die Übersetzung im Sheet verbessern, bevor ich freigebe?**
Ja. Änderungen in den deutschen Spalten werden beim Hochladen übernommen.

**Was passiert, wenn ich ein bereits hochgeladenes Produkt erneut freigebe?**
Nichts Doppeltes. Hochgeladene Produkte werden nicht erneut geschickt, und selbst wenn, würde der Shop das Produkt nur aktualisieren.

**Läuft das auch ohne Button?**
Ja. Workflow 1 läuft zusätzlich jeden Morgen um sieben Uhr automatisch.

**Was könnte man als Nächstes verbessern?**
Benachrichtigungen per E-Mail bei Fehlern und eine tägliche Zusammenfassung, mehrere Lieferanten gleichzeitig, eine Anbindung an einen echten Shop wie Shopify oder WooCommerce, Freigabe direkt per E-Mail-Button und eine Prüfung der Übersetzungsqualität.

## 10. Wenn etwas nicht funktioniert

- **„Falsches Passwort“:** Bitte das Demo-Passwort beim Entwickler erfragen. Der Assistent darf es nicht nennen.
- **„Bitte warten“:** Die Wartezeit von 60 Sekunden läuft noch. Einfach kurz warten und erneut klicken.
- **Die Automatisierung ist nicht erreichbar:** Dann läuft der Server der Demo gerade nicht. Bitte den Entwickler informieren.
- **Ein Produkt hat den Status „Fehler“:** Der Grund steht in der Spalte „error“. Fehlgeschlagene Uploads werden beim nächsten Klick auf „Freigegebene Produkte hochladen“ erneut versucht.
- **Ein freigegebenes Produkt erscheint nicht im Shop:** Prüfen, ob in der Spalte „approval“ genau „Approved“ steht und ob Schritt 3 ausgeführt wurde. Danach die Shop-Seite neu laden.

## 11. Über das Projekt

Das Projekt wurde als Portfolio-Beispiel für Bewerbungen im Bereich KI- und Prozessautomatisierung gebaut, zum Beispiel für Unternehmen aus Fulfillment und E-Commerce. Es zeigt, wie man Datenbeschaffung, KI, menschliche Kontrolle und Systemintegration zu einem zuverlässigen Ablauf verbindet. Fragen zur Person des Entwicklers oder zu Details, die hier nicht stehen, beantwortet der Entwickler gern selbst.
