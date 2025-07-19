# EVE Data Extractor
I designed this script to help me extract specific fields from EVE's Static Data Export(SDE) and the Image Export Collection from 2023.

The data from this script is used to help build 3rd party apps or websites with desired data. These apps/sites do not actively use this script or its data. Instead, you use this script to pull down assets(like icons, or yaml files) and move the assets into your project folder.

## Static Data Export (SDE)
CCP periodically releases an SDE for game assets.

Note: SDE is not live data. It is STATIC data. So things like: region names, system names, station names, market categories, market item names. Along with these names are many other fields of interest to those that want to build their own data collection or data search tools.

SDE Link: https://developers.eveonline.com/docs/services/sde/ (too large to keep in here)

## EVE Swagger Interface (ESI)
If you are wanting to retrieve live game data, such as market orders & prices, jump gate usage, etc. Then your data tool or script will need to pull data from the Tranquility server.

This is done by accessing the games API known as EVE Swagger Interface (ESI)

ESI Link: https://esi.evetech.net/ui/

## Image Export Collection
https://developers.eveonline.com/docs/services/iec/

I will also keep a copy of this download here in this repo.

•	Open these 2 files from the SDE
o	marketGroups.yaml
o	iconIDs.yaml
•	Open the unzipped image export collection folder.

•	Search marketGroups.yaml for a group name (Example: Manufacture & Research)
•	Copy the iconID from marketGroups.yaml (Example: 1436)
•	Search iconIDs.yaml for the iconID
•	Copy the path file name at the end of the path for the iconFile (Example: 27_64_1.png)
•	In the image export collection folder, do a search for the iconFile name.
•	You may get a few results, but what you want is the name that is an exact match.

