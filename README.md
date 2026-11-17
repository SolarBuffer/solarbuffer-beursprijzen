# SolarBuffer Beursprijzen voor Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)

De stroom- en gasprijs per uur voor wie een dynamisch energiecontract heeft. Je
kiest bij het instellen je leverancier en krijgt dan de prijs die je werkelijk
betaalt: de beursprijs plus de inkoopopslag van je leverancier, energiebelasting
en btw.

Je hebt hier geen SolarBuffer voor nodig. Iedereen kan hem gebruiken.

## Installatie

[![Open je Home Assistant en voeg deze repository toe aan HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=SolarBuffer&repository=solarbuffer-beursprijzen&category=integration)

Klik op de knop hierboven, kies Download en herstart Home Assistant. Voeg
daarna de integratie toe:

[![Begin met instellen.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=solarbuffer_beursprijzen)

Kies je leverancier uit de lijst, of Alleen de beursprijs. Van leverancier
wisselen kan later via Configureren, zonder iets opnieuw in te stellen. Wil je
leveranciers vergelijken, voeg de integratie dan meerdere keren toe.

<details>
<summary>Handmatig, zonder HACS</summary>

Kopieer de map `custom_components/solarbuffer_beursprijzen` naar de map
`custom_components` van je Home Assistant en herstart.

</details>

## Sensoren

| Sensor | Wat |
|---|---|
| Stroomprijs | De all-in prijs van dit uur, in EUR/kWh |
| Stroomprijs volgend uur | De prijs van het uur hierna |
| Laagste, hoogste en gemiddelde stroomprijs vandaag | Over de hele dag |
| Goedkoopste uur | Het goedkoopste uur dat nog komt, met de prijs als attribuut |
| Duurste uur | Het duurste uur dat nog komt |
| Beursprijs | De kale prijs van de beurs, incl. btw, zonder opslag en belasting |
| Gasprijs | De all-in gasprijs, in EUR/m³ |
| Goedkoopste leverancier nu | Wie dit uur het goedkoopst is, met de hele ranglijst als attribuut |

De sensoren Stroomprijs, Beursprijs en Gasprijs hebben de attributen `vandaag`
en `morgen`, een lijst met per uur `start`, `eind` en `prijs`. De prijzen van
morgen komen elke middag rond 13:00 binnen; tot dan is `morgen_beschikbaar`
false.

Stroomprijs kun je in het Energiedashboard gebruiken als de prijs van je
afgenomen stroom, en Gasprijs als de prijs van je gas.

## Voorbeelden

De wasmachine pas starten in het goedkoopste uur:

```yaml
automation:
  - alias: Wasmachine in het goedkoopste uur
    triggers:
      - trigger: time
        at: sensor.beursprijzen_goedkoopste_uur
    actions:
      - action: switch.turn_on
        target:
          entity_id: switch.wasmachine
```

Een grafiek van vandaag en morgen met [ApexCharts Card](https://github.com/RomRider/apexcharts-card):

```yaml
type: custom:apexcharts-card
graph_span: 48h
span:
  start: day
now:
  show: true
series:
  - entity: sensor.beursprijzen_stroomprijs
    type: column
    data_generator: |
      return [...entity.attributes.vandaag, ...entity.attributes.morgen]
        .map(u => [new Date(u.start).getTime(), u.prijs]);
```

De entiteit-id's hangen af van de naam van je leverancier; kijk bij Apparaten
en diensten hoe ze bij jou heten.

## Waar de prijzen vandaan komen

De integratie haalt de prijzen een keer per uur op bij de openbare
prijzendienst van SolarBuffer. Tussen 13:00 en 15:00 kijkt hij elk kwartier,
tot de prijzen van morgen binnen zijn. De dienst kun je ook als pagina bekijken op
[hub.solarbuffer.nl/energieprijzen](https://hub.solarbuffer.nl/energieprijzen).
De beursprijs komt van [EnergyZero](https://www.energyzero.nl), de inkoopopslag
per leverancier van [energieprijzen-nl](https://github.com/zhinees/energieprijzen-nl)
onder CC BY 4.0. Er gaat geen informatie over jou of je Home Assistant mee.

De prijzen zijn een zo goed mogelijke berekening. Je leverancier kan andere
kosten rekenen, zoals vaste leveringskosten, die hier niet in zitten.
