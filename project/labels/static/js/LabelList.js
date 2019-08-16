/* The following "singleton" design pattern is from
 * http://stackoverflow.com/a/1479341/
 */
var LabelList = (function() {

    var $labelTable = null;
    var $searchStatus = null;
    var $searchForm = null;
    var searchFieldTypingTimer = null;


    function get$row(labelId) {
        return $labelTable.find('tr[data-label-id="{0}"]'.format(labelId));
    }


    function submitSearch() {
        var formData = new FormData($searchForm[0]);

        $.get(
            // URL to make request to
            $searchForm.attr('data-url'),
            // Data to send in the request; seems that $.get() can't take a
            // FormData, so we have to convert to an Object.
            // (Using $.ajax() instead of $.get() should allow us to pass a
            // FormData, but for some reason I couldn't get that use case to
            // work with a GET request. -Stephen)
            {'name_search': formData.get('name_search')},
            // Callbacks
            handleSearchResponse
        ).fail(util.handleServerError);

        $searchStatus.text("Searching...");
    }


    function handleSearchResponse(jsonResponse) {
        // Hide all rows (except the table header row)
        $labelTable.find('tr:not(:first-child)').hide();

        if (jsonResponse['error']) {
            $searchStatus.text(jsonResponse['error']);
            return;
        }

        var labelIds = jsonResponse['label_ids'];

        // Show matching rows
        var i;
        for (i = 0; i < labelIds.length; i++) {
            get$row(labelIds[i]).show();
        }

        if (labelIds.length > 0) {
            $searchStatus.text("{0} results found:".format(labelIds.length));
        }
        else {
            $searchStatus.text("No results.");
        }
    }


    /* Public methods.
     * These are the only methods that need to be referred to as
     * <SingletonClassName>.<methodName>. */
    return {
        init: function() {
            $labelTable = $('#label-table');

            $searchStatus = $('#label-search-status');
            $searchForm = $('#search-form');

            // Update search results 0.75s after changing a field
            var timeout = 750;
            $searchForm.find('input').keyup(function() {
                clearTimeout(searchFieldTypingTimer);
                searchFieldTypingTimer = setTimeout(submitSearch, timeout);
            });
        }
    }
})();
