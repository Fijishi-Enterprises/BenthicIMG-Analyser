/* Dependencies: jQuery, util */


/* If there are media to be asynchronously loaded, then load them. */
util.addLoadEvent( function() {
    // Async media = Images that have the media-async class and
    // a non-blank hash attribute.
    var $asyncMedia =
        $('img.media-async[data-async-request-hash!=""]');
    if ($asyncMedia.length === 0) { return; }

    var requestHashes = [];
    $asyncMedia.each(function() {
        requestHashes.push($(this).attr('data-async-request-hash'));
    });

    var handlePollForMediaResponse = function(response) {
        var i;
        for (i = 0; i < response['media'].length; i++) {
            var thumb = response['media'][i];
            // Load the newly-generated media file's URL into the
            // img element.
            // We get the index from the server side because responses
            // could potentially arrive here out of order.
            $asyncMedia[thumb['index']].src = thumb['url'];
        }

        if (response['mediaRemaining']) {
            // There are more media to get; keep polling the server.
            window.setTimeout(pollForMedia, 2*1000);
        }
    };
    var pollForMedia = function() {
        $.ajax({
            // URL to make request to
            url: window.pollForMediaURL,
            // Data to send in the request.
            // The server uses the hash of the first requested media file
            // as the file-retrieval-progress key.
            data: {'first_hash': requestHashes[0]},
            type: 'POST',
            // Callbacks
            success: handlePollForMediaResponse,
            error: util.handleServerError
        });
    };

    // Request generation of all the media this page requires.
    $.ajax({
        // URL to make request to
        url: window.generateMediaURL,
        // Data to send in the request.
        // The server uses the hashes to identify which media
        // are being requested.
        data: {'hashes': requestHashes},
        type: 'POST',
        // Callbacks
        // Media are retrieved from the polling responses,
        // so no success callback is needed here.
        error: util.handleServerError
    });
    // Start periodically checking the server for generated media.
    // This is more responsive than retrieving all media once they're
    // all finished.
    // It's also more efficient than having the server return to us and wait
    // for another request after each media file.
    window.setTimeout(pollForMedia, 2*1000);
});
