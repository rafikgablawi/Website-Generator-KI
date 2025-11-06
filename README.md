# 🧠 Website-Generator KI

Mit dem **Website-Generator KI** kannst du ganz einfach individuelle Webseiten generieren lassen – einfach Beschreibung eingeben und die KI erstellt HTML für dein Wunsch-Projekt.

## Features

- **KI-gestützte HTML-Generierung:** Beschreibe deine Wunschwebsite und erhalte voll funktionsfähigen HTML-Code.
- **Live-Vorschau:** Das KI-generierte Ergebnis wird direkt auf der Seite angezeigt.
- **Modellauswahl:** Nutze verschiedene Ollama-Modelle (Standard: `qwen3-coder:480b-cloud`), anpassbar im Eingabefeld.
- **Token-Limit konfigurierbar:** Steuere die maximale Ausgabegröße für die KI.
- **Speichern als HTML:** Lade deinen Website-Entwurf als HTML-Datei herunter.

## Wie funktioniert es?

1. **Beschreibung eingeben:** Formuliere im Textfeld, wie deine Website aussehen soll (z. B. „Moderne Homepage für Studio Aurora mit Hero, Leistungen, Kontakt“).
2. **Modell & Tokens einstellen (optional):** Passe das verwendete KI-Modell und die `max_tokens`-Grenze nach Bedarf an.
3. **Website erstellen:** Klicke auf **Website erstellen** – die KI generiert automatisch einen HTML-Vorschlag.
4. **Speichern:** Mit **Als HTML speichern** kannst du den Vorschlag direkt herunterladen.

## Installation & Nutzung

1. **Backend bereitstellen:** Du benötigst eine Server-komponente, die die `POST /generate`-API bereitstellt und die KI-Anfrage verarbeitet.
2. **Projekt klonen:**
   ```bash
   git clone https://github.com/rafikgablawi/Website-Generator-KI.git
   ```
3. **Frontend öffnen:** Die `index.html` kann statisch gehostet werden. Öffne sie einfach im Browser. (Für die Generierung ist das Backend erforderlich.)

## API-Spezifikation

Die Anwendung erwartet ein Backend-Endpunkt:

```
POST /generate
Content-Type: application/json
Body: {
  "prompt": "Beschreibung der Website",
  "model": "Modell-Name",
  "max_tokens": 1000
}
Antwort: {
  "html": "<dein generiertes HTML>"
}
```

## Beispiel-Beschreibungen

- „Portfolio für einen Fotografen mit Galerie, Über mich und Kontaktformular.“
- „Landingpage für App ‚TimeHero‘, große Überschrift, Features, Preis, Call-to-Action.“
- „Business-Website für Architekturbüro, Teamvorstellung, Projekte, Kontakt.“

## Lizenz

MIT

---

**Von [rafikgablawi](https://github.com/rafikgablawi)**
