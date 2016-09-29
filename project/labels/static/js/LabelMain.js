var LabelMain = (function() {

    var patchesUrl = null;
    var nextPatchesPage = null;

    var $patchesContainer = null;
    var $patchLoadingStatus = null;
    var $getMorePatchesButton = null;


    function requestPatches() {
        $.get(
            patchesUrl,
            {'page': nextPatchesPage},
            handlePatchesResponse
        ).fail(util.handleServerError);

        $patchLoadingStatus.text("Loading patches...");
        $getMorePatchesButton.disable();
    }

    function handlePatchesResponse(jsonResponse) {
        $patchLoadingStatus.empty();

        // The HTML returned doesn't have a root node.
        // Fix that for easier jQuery handling.
        var $htmlResponse =
            $('<div>' + jsonResponse['patchesHtml'] + '</div>');
        var children = $htmlResponse.children();

        if (children.length > 0) {
            children.each(function () {
                $patchesContainer.append($(this));
            });
        }

        if (jsonResponse['isLastPage']) {
            $getMorePatchesButton.disable();
            $getMorePatchesButton.attr('title', "Already fetched all patches");
        }
        else {
            $getMorePatchesButton.enable();
            nextPatchesPage += 1;
        }
    }


    /* Public methods.
     * These are the only methods that need to be referred to as
     * <SingletonClassName>.<methodName>. */
    return {
        init: function(params) {
            patchesUrl = params['patchesUrl'];
            nextPatchesPage = 1;
            $patchesContainer = $('#patches-container');
            $getMorePatchesButton = $('#get-more-patches-button');
            $patchLoadingStatus = $('#patch-loading-status');

            $getMorePatchesButton.click(requestPatches);

            requestPatches();
        }
    }
})();
