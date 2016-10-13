/* The following "singleton" design pattern is from
 * http://stackoverflow.com/a/1479341/
 */
var LabelList = (function() {

    var $labelTable = null;
    var $searchStatus = null;
    var $searchField = null;
    var searchFieldTypingTimer = null;


    function get$row(labelId) {
        return $labelTable.find('tr[data-label-id="{0}"]'.format(labelId));
    }


    function submitSearch(searchValue) {
        if (searchValue.length <= 0) {
            // Show all rows
            $labelTable.find('tr').show();
            $searchStatus.text("");
            return;
        }

        $.get(
            $searchField.attr('data-url'),
            {'search': searchValue},
            handleSearchResponse
        ).fail(util.handleServerError);
        $searchStatus.text("Searching...");
    }


    function handleSearchResponse(jsonResponse) {
        var labelIds = jsonResponse['label_ids'];

        // Hide all rows (except the table header row)
        $labelTable.find('tr:not(:first-child)').hide();

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
            $searchField = $('#label-search-field');

            // Update search results 0.75s after typing in the field
            $searchField.keyup(function() {
                clearTimeout(searchFieldTypingTimer);
                searchFieldTypingTimer = setTimeout(
                    submitSearch.curry($searchField.val()), 750);
            });
        }
    }
})();
