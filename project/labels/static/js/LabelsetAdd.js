/* The following "singleton" design pattern is from
 * http://stackoverflow.com/a/1479341/
 */
var LabelsetAdd = (function() {

    var labelIdsInAnnotations = null;

    var $labelsetLabelIdsField = null;
    var $unusedLabelElementsContainer = null;
    var $searchStatus = null;
    var $searchForm = null;


    function get$addBox(labelId) {
        return $('.label-add-box[data-label-id="{0}"]'.format(labelId));
    }
    function get$removeBox(labelId) {
        return $('.label-remove-box[data-label-id="{0}"]'.format(labelId));
    }
    function get$detailBox(labelId) {
        return $('.label-detail-box[data-label-id="{0}"]'.format(labelId));
    }

    function isSelected(labelId) {
        return $('#selected-label-container').find(
            'div[data-label-id="{0}"]'.format(labelId)).length > 0;
    }
    function isInSearch(labelId) {
        return $('#label-search-result-container').find(
            'div[data-label-id="{0}"]'.format(labelId)).length > 0;
    }
    function isInUse(labelId) {
        return isSelected(labelId) || isInSearch(labelId);
    }
    function isInAnnotations(labelId) {
        return labelIdsInAnnotations.indexOf(labelId) !== -1;
    }

    function getSelectedIds() {
        var $container = $('#selected-label-container');
        var ids = [];

        $container.children().each(function() {
            ids.push(Number($(this).attr('data-label-id')));
        });
        return ids
    }
    function getNumSelected() {
        var $container = $('#selected-label-container');
        return $container.children().length;
    }

    function enableAddButton(labelId) {
        var $addButton = get$addBox(labelId).find('.add-remove-button');
        $addButton.removeClass('disabled');
        $addButton.attr('title', "Add to labelset");
        $addButton.click(addLabelToSelected.curry(labelId));
    }
    function disableAddButton(labelId) {
        var $addButton = get$addBox(labelId).find('.add-remove-button');
        $addButton.addClass('disabled');
        $addButton.attr('title', "Label already in labelset");
        $addButton.unbind('click');
    }
    function enableRemoveButton(labelId) {
        var $addButton = get$removeBox(labelId).find('.add-remove-button');
        $addButton.removeClass('disabled');
        $addButton.attr('title', "Remove from labelset");
        $addButton.click(removeLabelFromSelected.curry(labelId));
    }
    function disableRemoveButton(labelId) {
        var $addButton = get$removeBox(labelId).find('.add-remove-button');
        $addButton.addClass('disabled');
        $addButton.attr('title', "Label used by annotations, can't remove");
        $addButton.unbind('click');
    }


    function submitSearch() {
        var searchValue = $searchForm.find('input[name="search"]').val();
        if (searchValue === '') { return; }

        removeAllLabelsFromSearch();

        $.get(
            $searchForm.attr('action'),
            {'search': searchValue},
            handleSearchResponse
        ).fail(util.handleServerError);
    }


    function handleSearchResponse(htmlResponse) {
        // The response here doesn't have a root node.
        // Fix that for easier jQuery parsing.
        var $htmlResponse = $('<div>' + htmlResponse + '</div>');
        var children = $htmlResponse.children();

        if (children.length > 0) {
            $searchStatus.text("{0} results found:".format(children.length));
            children.each(function () {
                var labelId = addResponseLabelToPage($(this));
                addLabelToSearch(labelId);
            });
        }
        else {
            $searchStatus.text("No results.");
        }
    }


    function addResponseLabelToPage($labelContainer) {
        var $labelAddBox = $labelContainer.find('.label-add-box');
        var $labelRemoveBox = $labelContainer.find('.label-remove-box');
        var $labelDetailBox = $labelContainer.find('.label-detail-box');

        var labelId = Number($labelAddBox.attr('data-label-id'));

        if (isInUse(labelId)) {
            // The label is already on the page. This container just provides
            // duplicate elements.
            $labelContainer.remove();
            return labelId;
        }

        $unusedLabelElementsContainer.append($labelAddBox);
        $unusedLabelElementsContainer.append($labelRemoveBox);
        $unusedLabelElementsContainer.append($labelDetailBox);

        // Detail-button click handlers
        $labelAddBox.find('.detail-button').click(
            showLabelDetail.curry(labelId)
        );
        $labelRemoveBox.find('.detail-button').click(
            showLabelDetail.curry(labelId)
        );

        // Add/remove handlers
        enableAddButton(labelId);
        enableRemoveButton(labelId);

        // We've moved or used all the container elements, so no use for the
        // container anymore
        $labelContainer.remove();

        return labelId;
    }


    function removeLabelFromPage(labelId) {
        get$addBox(labelId).remove();
        get$removeBox(labelId).remove();
        get$detailBox(labelId).remove();
    }


    function addLabelToSearch(labelId) {
        if (isInSearch(labelId)) { return; }

        // Add label-add box to selected.
        // We'll just assume this function is called such that the labels
        // stay in the desired order.
        $('#label-search-result-container').append(get$addBox(labelId));
    }


    function removeAllLabelsFromSearch() {
        $('#label-search-result-container').children().each(function() {
            var labelId = Number($(this).attr('data-label-id'));

            if (isSelected(labelId)) {
                // Only remove add box from search area
                $('#unused-label-elements-container').append(
                    get$addBox(labelId));
            }
            else {
                // Remove all boxes from page
                removeLabelFromPage(labelId);
            }
        });
    }


    function addLabelToSelected(labelId) {
        if (isSelected(labelId)) { return; }

        /* TODO: Maintain an ordering to the labels based on their names.
         * May involve using insertAfter(). */

        // Add label-remove box to selected
        $('#selected-label-container').append(get$removeBox(labelId));

        // Hide label-add box
        $('#unused-label-elements-container').append(get$addBox(labelId));

        // Update number of labels display
        $('#selected-label-count').text(getNumSelected());

        // Update the labelset form's field
        $labelsetLabelIdsField.val(getSelectedIds().join(','));

        // Disable the add button for this label
        disableAddButton(labelId);

        if (isInAnnotations(labelId)) {
            disableRemoveButton(labelId);
        }
    }


    function removeLabelFromSelected(labelId) {
        if (!isSelected(labelId)) { return; }

        // Hide label-remove box
        $('#unused-label-elements-container').append(get$removeBox(labelId));

        // Update number of labels display
        $('#selected-label-count').text(getNumSelected());

        // Update the labelset form's field
        $labelsetLabelIdsField.val(getSelectedIds().join(','));

        // Re-enable the add button for this label
        enableAddButton(labelId);

        if (!isInUse(labelId)) {
            removeLabelFromPage(labelId);
        }
    }


    function showLabelDetail(labelId, event) {
        var $detailBox = get$detailBox(labelId);
        $detailBox.dialog({
            position: {my: 'left top', of: event, collision: 'fit'},
            width: 400,
            height: 300,
            modal: false
        });
    }


    /* Public methods.
     * These are the only methods that need to be referred to as
     * <SingletonClassName>.<methodName>. */
    return {
        init: function(params) {
            labelIdsInAnnotations = params['labelIdsInAnnotations'];

            $labelsetLabelIdsField = $('#id_label_ids');
            $unusedLabelElementsContainer =
                $('#unused-label-elements-container');

            $('#initial-label-container').children().each(function() {
                var labelId = addResponseLabelToPage($(this));
                addLabelToSelected(labelId);
            });

            $('#new-label-form-show-button').click(function() {
                $('#new-label-form-popup').dialog({
                    width: 600,
                    height: 400,
                    modal: false
                });
            });

            $searchStatus = $('#label-search-status');
            $searchForm = $('#label-search-form');
            $searchForm.submit(function() {
                try {
                    submitSearch();
                }
                catch (e) {
                    // Don't crash on an error so that we can
                    // return from this function as planned.
                    // This makes error logging a bit less nice though.
                    console.log(e);
                }
                // Don't let the form do a non-Ajax submit.
                return false;
            });
        },

        afterLabelCreated: function(htmlResponse) {
            // The response here should only have one top-level node,
            // corresponding to the one label that was created.
            var labelId = addResponseLabelToPage($(htmlResponse));
            addLabelToSelected(labelId);
        }
    }
})();
