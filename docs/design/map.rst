Map of sources
==============


Why we switched from Google Maps to Leaflet + OpenStreetMap:

- Google Maps required a Google account, and an API key associated with that account stored in Google Cloud Platform. Care had to be taken to use the API key securely, as well. OpenStreetMap needs no API key to use their map tiles; they just ask for attribution and to not go overboard with server requests (see below).

- The Leaflet plugin is compatible with different map-tile providers besides OpenStreetMap, and OpenStreetMap tiles can be used with plugins besides Leaflet. So each component is replaceable and there's less vendor lock-in.

- Switching to Leaflet + OpenStreetMap with nearly equal functionality, including replacing markerclusterer, turned out to be a relatively quick process. And the old map code needed modernizing either way.

- Fewer Google products means a smaller tracking footprint in the browser.

OpenStreetMap copyright, license, and terms can be found from `here <https://www.openstreetmap.org/copyright>`__. Notes:

- Attribution-text details can be found `here <https://osmfoundation.org/wiki/Licence/Attribution_Guidelines#Attribution_text>`__

- Notes on their `tile policy <https://operations.osmfoundation.org/policies/tiles/>`__:

  - "Heavy use (e.g. distributing a heavy-usage app that uses tiles from openstreetmap.org) is forbidden without prior permission from the Operations Working Group. See below for alternatives."

  - "Bulk downloading is strongly discouraged. Do not download tiles unnecessarily. In particular, downloading an area of over 250 tiles at zoom level 13 or higher for offline or later usage is forbidden. These tiles are generally not available (cached) on the server in advance, and have to be rendered specifically for those requests, putting an unjustified burden on the available resources."

    - We cap the zoom level at 9.

  - "Recommended: Do not hardcode any URL to tile.openstreetmap.org as doing so will limit your ability to react if the service is disrupted or blocked. In particular, switching should be possible without requiring a software update."

    - We should at least keep an eye on map-tile disruptions to see how useful it would be to implement switching.
