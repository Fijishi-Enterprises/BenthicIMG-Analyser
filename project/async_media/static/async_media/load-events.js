/* Dependencies: jQuery, util */


/* If there are thumbnails to be asynchronously loaded, then load them. */
util.addLoadEvent( function() {
    // Async thumbnails = Images that have the thumb-async class and
    // a non-blank hash attribute.
    var $asyncThumbnails =
        $('img.thumb-async[data-async-request-hash!=""]');
    if ($asyncThumbnails.length === 0) { return; }

    var requestHashes = [];
    $asyncThumbnails.each(function() {
        requestHashes.push($(this).attr('data-async-request-hash'));
    });

    var handlePollForThumbnailsResponse = function(response) {
        var i;
        for (i = 0; i < response['thumbnails'].length; i++) {
            var thumb = response['thumbnails'][i];
            // Load the newly-generated thumbnail's URL into the
            // img element.
            // We get the index from the server side because responses
            // could potentially arrive here out of order.
            $asyncThumbnails[thumb['index']].src = thumb['url'];
        }

        if (response['thumbnailsRemaining']) {
            // There are more thumbnails to get; keep polling the server.
            window.setTimeout(pollForThumbnails, 2*1000);
        }
    };
    var pollForThumbnails = function() {
        $.ajax({
            // URL to make request to
            url: window.pollForThumbnailsURL,
            // Data to send in the request.
            // The server uses the hash of the first requested thumbnail
            // as the thumbnail-progress key.
            data: {'first_hash': requestHashes[0]},
            type: 'POST',
            // Callbacks
            success: handlePollForThumbnailsResponse,
            error: util.handleServerError
        });
    };

    // Request generation of all the thumbnails this page requires.
    $.ajax({
        // URL to make request to
        url: window.generateThumbnailsURL,
        // Data to send in the request.
        // The server uses the hashes to identify which thumbnails
        // are being requested.
        data: {'hashes': requestHashes},
        type: 'POST',
        // Callbacks
        // Thumbnails are retrieved from the polling responses,
        // so no success callback is needed here.
        error: util.handleServerError
    });
    // Start periodically checking the server for generated thumbnails.
    // This is more responsive than retrieving all thumbnails once they're
    // all finished.
    // It's also more efficient than having the server return to us and wait
    // for another request after each thumbnail.
    window.setTimeout(pollForThumbnails, 2*1000);
});
