# Discord Fix-zijpaneel voor Chrome en Edge

De browserextensie toont Discord Fix naast Discord in een gewone Chrome- of Edge-browser. Discord zelf blijft onaangeraakt. Het zijpaneel leest alleen het lokale, alleen-lezen dashboard van de geopende Discord Fix-desktopapp. Het leest geen Discord-tabbladen, gebruikt geen Discord-login of gebruikerstoken en verstuurt of wijzigt geen berichten.

De extensie heeft geen toegang tot Discord nodig. Pas wanneer je een lokale dashboardlink invoert, vraagt de browser toestemming voor `http://127.0.0.1` zodat de extensie jouw eigen Discord Fix-app kan bereiken. De dashboardlink bevat een tijdelijke, willekeurige toegangscode en wordt lokaal opgeslagen in de extensie. Deel die link niet.

De browsermachtiging voor `127.0.0.1` geldt technisch voor HTTP-poorten op dat lokale adres. De extensie vraagt die machtiging pas bij verbinden, controleert dat de ingevoerde link naar `127.0.0.1` en één toegangspad wijst, en haalt alleen het dashboard via GET op. **Verbinding wissen** trekt de machtiging weer in.

## De ontwikkelversie installeren

Deze versie is nog niet gepubliceerd in de Chrome Web Store of Microsoft Edge Add-ons. Laden als ontwikkelaar is bedoeld voor een lokale proef:

1. Start Discord Fix op Windows en klik op **Browserdashboard**. Laat de app open.
2. Kopieer de volledige `http://127.0.0.1:...`-link uit de adresbalk.
3. Open `chrome://extensions` in Chrome of `edge://extensions` in Edge en schakel **Developer mode / Ontwikkelaarsmodus** in.
4. Kies **Load unpacked / Uitgepakte extensie laden** en selecteer de map `browser-extension` uit deze repository.
5. Open het extensiepaneel met het Discord Fix-pictogram in de browserwerkbalk of extensiemenu. Plak de lokale dashboardlink en kies **Verbinden**. Sta de gevraagde toegang tot de lokale server toe als je verder wilt.

De zijbalk blijft gegevens vernieuwen zolang Discord Fix openstaat. Sluit je Discord Fix af en start je het later opnieuw, open dan opnieuw **Browserdashboard** en verbind de nieuwe link. De vorige lokale link vervalt wanneer de app sluit.

## Wat je kunt instellen

In **Jouw weergave** kies je donker, licht of systeemthema, ruime of compacte berichtregels, tellers voor prioriteiten en de status van databronnen. De extensie onthoudt deze voorkeuren alleen in de lokale extensieopslag van de browser. De vijf dashboardweergaven en de zoekfunctie werken op de gegevens die al in Discord Fix staan. Een berichtlink opent het originele Discord-bericht in een nieuw tabblad.

Het paneel is alleen-lezen: prioriteiten aanpassen en berichten afhandelen doe je nog in de Discord Fix-desktopapp. De huidige desktopapp is dus nodig voor het lokale dashboard en de gegevensbron.

## Reikwijdte

De browser-zijbalk neemt ruimte naast de webpagina in en verandert Discord niet. Ze werkt niet in de Discord-desktopapp, op mobiel of in de ingebouwde ChatGPT-browser. Een extensie die Discords pagina-inhoud herschikt, verbergt of vervangt, is geen ondersteunde route: Discord verbiedt clientaanpassingen en het veranderen van de clientindeling.
