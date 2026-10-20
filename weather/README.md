# Rain Check

A one-page weather dashboard. It shows the current weather in the capital city of every country (197 capitals), and whether it is raining there right now.

## Features

- A summary strip: how many capitals have rain or snow right now, and the hottest and coldest capital.
- A card for each capital with temperature, conditions, local time, rainfall, humidity and wind.
- Search by country or capital, filter by Raining / Snowing / Dry, and sort by name, temperature or rainfall.
- °C / °F switch and a light / dark theme switch. Both choices are remembered in your browser.
- Data refreshes every 15 minutes, or whenever you press **Refresh now**.

Weather data comes from [Open-Meteo](https://open-meteo.com/), which is free and needs no API key.

## Run

The whole app is one file, `index.html`. There is nothing to install or build.

**Option 1: open the file.** Double-click `index.html`, or open it from your browser's File menu.

**Option 2: serve it locally.** Some browsers limit pages opened straight from disk, so if Option 1 shows no data, run a small local server from this folder:

```bash
cd weather
python3 -m http.server 8080
```

Then open http://localhost:8080.

You need an internet connection, because the page fetches live weather from Open-Meteo when it loads. If it can't reach the service, it shows an error. Press **Refresh now** to try again.
