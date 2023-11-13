class SourcesMap {

    constructor(mapSources) {
        // Render the map in this element.
        let mapElement = document.getElementById('map');

        // This center is chosen so that the relatively empty latitude
        // range between US west coast and Hawaii is at the edge of the
        // map.
        let center = [12.0, 40.0];
        // Zoom level 2 shows exactly one Earth when the map is
        // displayed at around 1024 x 1024 pixels.
        // The page width for the map is 984 pixels. In theory then,
        // an initial zoom of 2*(984/1024) would show exactly one
        // Earth, but in practice we have to adjust the zoom by about 0.02
        // from there.
        let initialZoom = 2*(984/1024) + 0.02;

        // Create Leaflet map.
        this.map = L.map(mapElement, {
            // How much the zoom level changes from the +/- buttons or
            // a double-click.
            zoomDelta: 1.0,
            // The zoom level snaps to multiples of this value if it's
            // above 0. If it is 0, then the zoom level can be an
            // arbitrary fractional value.
            zoomSnap: 0,
        }).setView(center, initialZoom);

        // Add OpenStreetMap tile layer to the map.
        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
            // Don't set this too low, or people could see Earth
            // wrapping around multiple times on the map.
            minZoom: initialZoom,
            // Don't set this too high, so people don't get lost after
            // clicking a bunched-together map cluster, and also because
            // OpenStreetMap gets more concerned about usage when
            // serving tiles at higher zoom levels.
            maxZoom: 9,
            attribution: 'Map data from <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        }).addTo(this.map);

        // Define marker icons.
        let aspectRatio = 50/82;
        let iconSizes = {
            // Original aspect ratio is (50, 82)
            1: new L.Point(22, 22/aspectRatio),
            2: new L.Point(26, 26/aspectRatio),
            3: new L.Point(30, 30/aspectRatio),
        };
        let iconStyles = {
            public: 'public-source',
            private: 'private-source',
        };
        // 2-D hash, indexed by size (1/2/3), then by type (public/private)
        let icons = {}
        for (let [sizeKey, size] of Object.entries(iconSizes)) {
            icons[sizeKey] = {}
            for (let [styleKey, styleClass] of Object.entries(iconStyles)) {
                let iconClass = L.Icon.Default.extend({
                    options: {
                        iconSize: size,
                        className: styleClass,
                    },
                });
                icons[sizeKey][styleKey] = new iconClass();
            }
        }

        // Place markers.

        let markers = L.markerClusterGroup();
        this.popup = L.popup({
            // For some reason, if only maxWidth is specified, a popup
            // for a particular source is more narrow on the first click
            // and wider the second click. Setting both min and max
            // prevents that oddity.
            // TODO: It still only pans up to make the top of the popup
            //  visible on the second click, not the first.
            minWidth: 550, maxWidth: 550,
        });

        for (let source of mapSources) {
            let coordinates = [source['latitude'], source['longitude']];

            let marker = L.marker(
                coordinates,
                {icon: icons[source['size']][source['type']]},
            );

            // Click-handler for the marker.
            marker.addEventListener('click', (event) => {
                this.showSourceDetail(
                    source['detailBoxUrl'], coordinates);
            })

            markers.addLayer(marker);
        }

        this.map.addLayer(markers);
    }

    showSourceDetail(detailBoxUrl, coordinates) {
        this.popup
        .setLatLng(coordinates)
        .setContent("Getting source info...")
        .openOn(this.map);

        util.fetch(
            detailBoxUrl,
            {},
            (response) => {
                // Add the source-detail HTML to the map's popup
                let detailBoxContainer = document.createElement('div');
                detailBoxContainer.insertAdjacentHTML(
                    'afterbegin', response['detailBoxHtml']);
                this.popup.setContent(detailBoxContainer);
            }
        )
    }
}
