# Discord Fix 0.4 — Windows-gebruikershandleiding

Dit is een werkende ontwikkelversie van de Phase 1-companion. De oorspronkelijke productvisie blijft in README.md staan. De app vervangt niet alle functies van Discord.

## Starten

Pak het Windows-pakket uit en open **DiscordFix.exe**. Python hoeft voor de uitvoerbare versie niet apart te worden geïnstalleerd. Je kunt de app ook met **Install-Discord-Fix.ps1** onder je eigen Windows-account installeren; het script maakt een Startmenu-snelkoppeling. De app slaat gegevens op in `%LOCALAPPDATA%\DiscordFix`. De build is nog niet digitaal ondertekend.

De inbox start leeg. Er worden geen accounts verbonden, berichten verzonden of betaalde modellen gebruikt zonder instellingen van jou. De screenshot bij de release gebruikt uitsluitend synthetische voorbeeldtekst.

## Browserdashboard

Kies **Browserdashboard** in Discord Fix om een dashboard in je browser te openen. De server luistert alleen op deze computer, gebruikt een tijdelijke geheime link en toont de bestaande lokale gegevens. De pagina is alleen-lezen en ververst automatisch ongeveer iedere 15 seconden. Sluit Discord Fix om de lokale dashboardsessie te stoppen. Deze pagina verbindt zelf niet met Discord en stuurt geen gegevens naar een andere dienst.

Voor een apart paneel naast Discord in Chrome of Edge kun je de lokale ontwikkelversie van de [browserextensie](BROWSER-EXTENSION.md) laden. De installatiehandleiding is Engels. De extensie wijzigt de Discord-pagina niet en vraagt alleen lokale toegang om dit dashboard op te halen.

## Je eigen export importeren

Kies **Discord-datapakket importeren** en selecteer je eigen ZIP-bestand. Ondersteund zijn de per-kanaalbestanden `messages.json` en de oudere `messages.csv`, naast `channel.json`. Ongeldige records komen in een volledig importverslag; geldige records kunnen worden opgeslagen. Onbekende structuren worden niet als geslaagde import voorgesteld. Archieven worden niet uitgepakt en bijlagen worden niet gedownload.

Een persoonlijk Discord-datapakket bevat je eigen verzonden berichten. Het is dus geen volledige inbox met de antwoorden van anderen. Zie de [officiële beschrijving van het datapakket](https://support.discord.com/hc/en-us/articles/360004957991-Your-Discord-Data-Package). De adapter is getest met synthetische formaten; een door jou aangeleverd echt pakket is nog niet gebruikt voor acceptatie.

Herimport werkt berichtinhoud bij en bewaart je handmatige prioriteit, opvolging en afhandelstatus. Een persoonlijke export overschrijft geen rijkere botgegevens.

## Een officiële bot verbinden

1. Laat een serverbeheerder een officiële Discord-bot installeren. Maak of beheer de bot in de [Discord Developer Portal](https://discord.com/developers/applications).
2. Verleen alleen de benodigde leestoegang: **View Channel** en **Read Message History**. Berichtinhoud kan daarnaast afhankelijk zijn van de Message Content-instelling/toegang van de applicatie.
3. Open **Bronnen → Bot toevoegen**. Voer de bot-tokenwaarde en de expliciet toegestane kanaal- of thread-ID's in.
4. Bevestig in het venster dat je deze bot en kanalen mag gebruiken. De app controleert de bot-identiteit en berekent de kanaalrechten voordat berichten worden gelezen.

De koppeling gebruikt uitsluitend GET-verzoeken naar de officiële Discord API. Gebruik geen persoonlijk gebruikerstoken. De app heeft geen algemene toegang tot je persoonlijke DM-inbox, geen verborgen scraping en geen schrijffunctie.

Per synchronisatie worden maximaal 500 recente berichten per gekozen kanaal opgehaald. Niet geselecteerde threads en oudere geschiedenis vallen buiten dat bereik. Bij bronfouten blijft bestaande lokale tekst beschikbaar, maar wordt die botbron uitgesloten van nieuwe samenvattingen. Rate limits leiden tot een wachttijd. Controle van bewerkingen/verwijderingen beperkt zich tot het opgehaalde bereik. Bij ontbrekende geschiedenisrechten wordt een lege lijst niet als bewijs van verwijdering gebruikt.

**Bronnen** toont de status, laatste ontvangst, bron-ID en dekking. **Loskoppelen** wist het lokale botgeheim; berichten blijven staan. **Lokaal verwijderen** vraagt afzonderlijk om bevestiging en verwijdert brongegevens en afgeleide overzichten, zonder iets in Discord te wijzigen.

## Dagelijks gebruik

- **Nu belangrijk:** automatische regels en je eigen prioriteitskeuze.
- **Opvolgen:** vermeldingen/antwoorden op jouw ingestelde gebruikers-ID en handmatige opvolging.
- **Gesprekken:** beschikbare berichten gegroepeerd per kanaal of expliciete thread.
- **Later:** uitgestelde berichten, die op het gekozen tijdstip terugkeren.
- **Alles:** chronologische controleweergave, inclusief afgehandelde items en verwijdermarkeringen.

Zoeken is standaard letterlijk. **Woorden** gebruikt de lokale volledige-tekstindex. Grote lijsten hebben pagina's van 200 berichten. **Ctrl+F** gaat naar zoeken. Vensters zijn scrollbaar en toetsenbordfocus wordt in beeld gebracht.

Bij **Instellingen → Weergave en meldingen** kun je kiezen uit Licht, Discord Ash, Discord Dark of Onyx zwart, en hoog contrast inschakelen. Bedienings- en berichttekst hebben aparte groottes; de lijst heeft compacte, standaard- en ruime regels. Sleep kolomranden om datum, kanaal, bericht en status afzonderlijk te verbreden of versmallen. Deze voorkeuren gelden alleen in Discord Fix; ze passen de officiële Discord-client niet aan. Sneltoetsen: **Ctrl+1–5** wisselt tussen de vijf dashboardweergaven, **Ctrl+Plus/Min** vergroot of verkleint tekst, **Ctrl+0** herstelt de standaardtekst en **F6** wisselt tussen zoeken, de berichtenlijst en details.

Bij ieder bericht kun je afhandelen, heropenen, negeren, belangrijk/opvolgen aanpassen, een tijdstip kiezen en een expliciete deadline zetten. Handmatige keuzes hebben voorrang; **Automatische regels herstellen** heft beide overrides op. Stel je eigen Discord-ID, belangrijke personen, servers, kanalen en onderwerpen in bij **Instellingen**.

**Volledige beschikbare context** toont de lokaal aanwezige berichten. **Origineel openen in Discord** is alleen beschikbaar als de oorspronkelijke link betrouwbaar opgebouwd kan worden. Antwoorden doe je in Discord.

## Contextoverzichten en AI

**Contextoverzichten → Verversen** maakt vier niveaus: gesprek/thread, kanaal, server en persoonlijk. Je kunt doorklikken naar onderliggende niveaus en oorspronkelijke berichten. De weergave vermeldt model, versie, verwerkingstijdstip, dekking en wijzigingen. Nieuwe nog niet verwerkte berichten worden apart geteld.

Beschikbare verwerkingsopties:

- **extractive:** lokale tekstregels, zonder AI-model. Toont letterlijke bronfragmenten en mogelijke vragen, besluiten of acties op basis van herkenbare tekst. Dit bewijst niet dat een uitspraak waar is of dat een vraag nog openstaat.
- **ollama:** een door jou geïnstalleerd lokaal model via `http://127.0.0.1:11434/api/chat`. Vul de echte modelnaam in. Er wordt niet automatisch een model gedownload.
- **external:** een door jou gekozen HTTPS-endpoint met een OpenAI-compatibel `/chat/completions`-contract, JSON-output en modelnaam. Toestemming is gebonden aan het exacte endpoint. Berichttekst, auteurs, tijdstippen, IDs en eerdere relevante samenvatting kunnen het apparaat verlaten. Providerkosten en het gegevensbeleid vallen onder jouw providercontract. De sleutel is apart per endpoint beveiligd opgeslagen.

AI-tekst wordt altijd als interpretatie aangeduid. Iedere samenvattingsclaim moet een bestaande bericht-ID en een letterlijk terugvindbaar citaat hebben. Dit controleert herleidbaarheid, niet automatisch de juistheid van de interpretatie. Onjuiste of ontbrekende bronverwijzingen laten de verwerking mislukken zonder berichten of het eerdere overzicht te verliezen.

Nieuwe tekst werkt het bestaande gespreksoverzicht bij. Bewerkte/verwijderde tekst dwingt volledige herverwerking van het betrokken gesprek af; periodiek vindt volledige reconciliatie plaats. **Volledig herberekenen** kan direct worden gebruikt. Hogere niveaus voegen lagere overzichten samen zonder nieuwe claims te verzinnen. Handmatige correcties worden afzonderlijk opgeslagen, met geschiedenis in de export.

Automatische synchronisatie en samenvatting staan standaard uit en werken alleen zolang de app open is. Het algemene interval staat bij Instellingen. **Bronnen → Interval** bepaalt een aanvullende minimale wachttijd per bron; controles gebeuren op het algemene interval. Model- of netwerkfouten worden zichtbaar en automatische taken proberen het bij hun volgende interval opnieuw.

## Privacy, opslag en herstel

Via **Privacy** kun je alle verwerking, een bron, server, kanaal, gesprek of bericht uitsluiten. Bovenliggende samenvattingen mogen uitgesloten tekst niet bevatten. Daarom verwijdert een privacywijziging bestaande overzichten én correcties voordat nieuwe worden opgebouwd. De originele lokale berichten blijven in Alles staan.

De SQLite-database valt onder de bescherming van je Windows-account; de berichtdatabase heeft geen extra applicatieversleuteling. Tokens worden met Windows DPAPI beveiligd. Er is geen telemetrie. Eén appinstantie kan tegelijk met dezelfde gegevensmap werken.

**Lokale gegevens exporteren** schrijft JSON met berichten, workflowstatussen, instellingen, bronnen en overzichten, zonder tokens. **Privacy → Databaseback-up maken** maakt een consistente SQLite-kopie. Bewaar exports en back-ups zorgvuldig: zij bevatten privégegevens en vallen niet onder latere verwijderingen of bewaartermijnen in de app.

Voor herstel: sluit de app, bewaar de huidige `discord-fix.sqlite` onder een andere naam en kopieer de gekozen back-up als `discord-fix.sqlite` naar dezelfde gegevensmap. Bewaar de map `secrets` op hetzelfde Windows-account als je bestaande koppelingen wilt behouden. Verhuisde secrets zijn niet zonder meer op een ander Windows-account te ontsleutelen. Herstel is een handmatige bestandsactie, geen knop in de app.

Een bewaartermijn van **0** betekent onbeperkt. Een andere termijn verwijdert na bevestiging lokaal oude berichten en hun afgeleide overzichten, ook als een bericht afgehandeld is. Eerder geëxporteerde kopieën worden niet aangepast.

## Wat nog geen live acceptatie heeft

De bot- en AI-adapters zijn gecontroleerd met synthetische transportcontracten. Nog niet getest met jouw echte Discord-bot, echte data-export of een echt generatief model. Screenreaderacceptatie en een ondertekende distributie ontbreken nog. Voice/video, mobiele clients, algemene persoonlijke DM-toegang en antwoorden vanuit Discord Fix vallen buiten de afgesproken eerste fase.

Discord Fix wijzigt de officiële Discord-client, diens overlay of de You Bar niet. Het biedt een eigen, rustiger overzicht van lokaal geïmporteerde of officieel toegankelijke informatie. Voor de native Discord-app blijven aanpassingen zoals een uitzetbare You Bar, herstel van de geïntegreerde game-overlay, verplaatsing van de Nitro-giftknop en onafhankelijke schaalinstellingen afhankelijk van Discord zelf of een officieel ondersteunde uitbreiding.
