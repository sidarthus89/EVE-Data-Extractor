# EVE Data Extractor
I designed this script to help me extract specific fields from EVE's Static Data Export(SDE) and the Image Export Collection from 2023.

The data from this script is used to help build 3rd party apps or websites with desired data. These apps/sites do not actively use this script or its data. Instead, you use this script to pull down assets(like icons, or yaml files) and move the assets into your project folder.

## Static Data Export (SDE)
CCP periodically releases an SDE for game assets.

Note: SDE is not live data. It is STATIC data. So things like: region names, system names, station names, market categories, market item names. Along with these names are many other fields of interest to those that want to build their own data collection or data search tools.

SDE Link: https://developers.eveonline.com/docs/services/sde/ 

## EVE Swagger Interface (ESI)
If you are wanting to retrieve live game data, such as market orders & prices, jump gate usage, etc. Then your data tool or script will need to pull data from the Tranquility server.

This is done by accessing the games API known as EVE Swagger Interface (ESI)

ESI Link: https://esi.evetech.net/ui/

## Image Export Collection
https://developers.eveonline.com/docs/services/iec/

I will also keep a copy of this download here in this repo.


•	Open marketGroups.yaml
•	Search for market group name (Example: Manufacture & Research)
•	Copy the marketGroupID from marketGroups.yaml (Example: 1436)
•	Open iconIDs.yaml and search for the copied marketGroupID
•	Copy the iconID from the iconIDs.yaml found by searching the marketGroupID. (Example: 
•	Open iconIDs.yaml for the marketGroupID (
•	Take the iconFile image name and search in the icons image export folder
•	Search for the iconFile image name.
•	The exact matched file name will be the icon used for that market group.

