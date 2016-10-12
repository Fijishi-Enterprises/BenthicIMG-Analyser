var CNMap = (function() {

    var map = null;
    var markers = [];

    var infoWindow = null;

    function getAndShowSourceDetail(detailBoxUrl, sourceLatLng) {
        if (infoWindow === null) {
            infoWindow = new google.maps.InfoWindow();
        }

        infoWindow.setPosition(sourceLatLng);
        infoWindow.setContent(
            document.createTextNode("Getting source info..."));
        infoWindow.open(map);

        $.get(
            detailBoxUrl,
            {},
            showSourceDetail.curry(infoWindow)
        ).fail(util.handleServerError);
    }

    function showSourceDetail(infoWindow, responseHtml) {
        // Parse the HTML and ensure it's in a root node
        var $detailBox = $('<div>' + responseHtml + '</div>');
        // Add the source-detail HTML to the map's info popup
        infoWindow.setContent($detailBox[0]);
    }

    return {

        init: function(params) {

            if (!google) {
                console.log("Couldn't load the Google API.");
                return;
            }

            // Map

            // https://developers.google.com/maps/documentation/javascript/tutorial#MapOptions
            var mapOptions = {
                center: new google.maps.LatLng(-10.5, -127.5),

                zoom: 2,
                minZoom: 2,
				maxZoom: 15,

                mapTypeId: google.maps.MapTypeId.SATELLITE
            };

            map = new google.maps.Map(
                document.getElementById("map-canvas"),
                mapOptions
            );

            // Legend

            var legend = document.getElementById('map-legend');

            map.controls[google.maps.ControlPosition.RIGHT_BOTTOM].push(legend);

            // Markers

            var i;

            for (i = 0; i < params['mapSources'].length; i++) {

                var source = params['mapSources'][i];
                var sourceLatLng = new google.maps.LatLng(
                    source['latitude'], source['longitude']);

                var markerSize = null;
                if (source['size'] === 1) {
                    markerSize = new google.maps.Size(20, 32);
                }
                else if (source['size'] === 2) {
                    markerSize = new google.maps.Size(25, 40);
                }
                else {  // 3
                    markerSize = new google.maps.Size(30, 48);
                }

                var markerIcon = null;
                if (source['type'] === 'public') {
                    markerIcon = staticmapimgs + "green.png";
                }
                else {  // 'private'
                    markerIcon = staticmapimgs + "red.png";
                }

                var marker = new google.maps.Marker({
                    position: sourceLatLng,
                    // This seems weird, but dragging does help to get at
                    // sources whose markers are hiding behind other markers.
                    draggable: true,
                    icon: new google.maps.MarkerImage(
                        markerIcon,
                        null,
                        null,
                        null,
                        markerSize
                    )
                });

                google.maps.event.addListener(
                    marker, 'click', getAndShowSourceDetail.curry(
                        source['detailBoxUrl'], sourceLatLng));
                markers.push(marker);
            }

            var markerCluster = new MarkerClusterer(
                map, markers, {maxZoom : 14});
        }
    }
})();
