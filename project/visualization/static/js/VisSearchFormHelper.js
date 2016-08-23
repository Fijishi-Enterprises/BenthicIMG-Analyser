var BrowseSearchHelper = (function() {

    var pageImageIds;
    var links;

    var $searchForm;
    var $actionForm;
    var $actionFormFieldContainer;
    var $actionFormBox;
    var $actionSelectField;
    var $actionSubmitButton;

    var dateFieldNameToIndex = {
        filter_type: 0,
        year: 1,
        date: 2,
        start_date: 3,
        end_date: 4
    };

    function get$dateField(name) {
        return $searchForm.find(
            'input[name=date_filter_{0}], select[name=date_filter_{0}]'.format(
                dateFieldNameToIndex[name]));
    }

    function onDateFilterTypeChange() {
        // Show different date sub-fields
        // according to the filter type value.
        var value = get$dateField('filter_type').val();

        if (value === 'year') {
            get$dateField('year').show();
            get$dateField('date').hide();
            get$dateField('start_date').hide();
            get$dateField('end_date').hide();
        }
        else if (value === 'date') {
            get$dateField('year').hide();
            get$dateField('date').show();
            get$dateField('start_date').hide();
            get$dateField('end_date').hide();
        }
        else if (value === 'date_range') {
            get$dateField('year').hide();
            get$dateField('date').hide();
            get$dateField('start_date').show();
            get$dateField('end_date').show();
        }
    }

    function onActionChange() {
        var action = $actionSelectField.val();

        // Show the 'specifics' element for only the selected action
        $('#action_form_annotate_specifics').hide();
        $('#action_form_delete_specifics').hide();
        $('#action_form_{0}_specifics'.format(action)).show();
    }

    function addActionFormField(name, value) {
        $actionFormFieldContainer.append($('<input/>', {
            type: 'hidden',
            name: name,
            value: value
        }));
    }
    function setActionFormUrl(url) {
        $actionForm.attr('action', url);
    }
    function areYouSureDelete() {
        return window.confirm(
            "Are you sure you want to delete these images?" +
            " You won't be able to undo this.");
    }
    function actionSubmit() {
        // Clear fields from any previous submit attempts.
        $actionFormFieldContainer.empty();

        var action = $actionSelectField.val();
        var imageSelectType =
            $actionFormBox.find('select[name=image_select_type]').val();

        // Note that the action form should just have a CSRF token initially;
        // we need to add the rest of the fields to it.
        // We add fields as hidden fields because the user doesn't have to
        // interact with them.
        if (action === 'annotate') {
            if (imageSelectType === 'all') {
                $('#previous-image-form-fields').find('input').each(
                    function () { addActionFormField(this.name, this.value); }
                );
                // Annotation tool for first image in the search
                setActionFormUrl(links['annotation_tool_first_result']);
            }
            else if (imageSelectType === 'selected') {
                addActionFormField('image_form_type', 'ids');
                addActionFormField('ids', pageImageIds.toString());
                // Annotation tool for first image on this page
                setActionFormUrl(links['annotation_tool_page_results'][0]);
            }

            $actionForm.submit();
        }
        else if (action === 'delete') {
            if (!areYouSureDelete()) { return; }

            var data = {};
            if (imageSelectType === 'all') {
                $('#previous-image-form-fields').find('input').each(
                    function () { data[this.name] = this.value; }
                );
            }
            else if (imageSelectType === 'selected') {
                data['image_form_type'] = 'ids';
                data['ids'] = pageImageIds.toString();
            }

            // This will run after deletion is complete.
            var callback = function(response) {
                if (response['error']) {
                    alert("Error: " + response['error']);
                    $actionSubmitButton.enable();
                    $actionSubmitButton.text("Go");
                    return;
                }

                // Re-fetch the current browse page.
                $('#previous-image-form-fields').find('input').each(
                    function () { addActionFormField(this.name, this.value); }
                );
                setActionFormUrl(links['browse']);

                $actionForm.submit();
            };

            // Delete images, then once it's done, run the callback.
            //
            // Since the first step is Ajax, let the user know what's going
            // on, and disable the button to prevent double submission.
            $actionSubmitButton.disable();
            $actionSubmitButton.text("Deleting...");
            $.post(links['delete'], data, callback);
        }
    }

    return {

        initSearchForm: function() {
            $searchForm = $('#search-form');

            /* Date filter fields. */
            // Add a handler.
            var $dateFilterTypeField = get$dateField('filter_type');
            $dateFilterTypeField.change(onDateFilterTypeChange);

            // Add datepickers.
            get$dateField('date').datepicker({dateFormat: 'yy-mm-dd'});
            get$dateField('start_date').datepicker({dateFormat: 'yy-mm-dd'});
            get$dateField('end_date').datepicker({dateFormat: 'yy-mm-dd'});

            // Initialize the date field appearance.
            onDateFilterTypeChange();
        },

        initActionForm: function(params) {
            pageImageIds = params['pageImageIds'];
            links = params['links'];

            $actionForm = $('#action-form');
            $actionFormBox = $('#action-form-box');
            $actionFormFieldContainer = $('#action-form-field-container');

            /* Action form. */
            // Add handlers.
            $actionSelectField =
                $actionFormBox.find('select[name=browse_action]');
            $actionSelectField.change(onActionChange);

            $actionSubmitButton = $('#action-submit-button');
            $actionSubmitButton.click(actionSubmit);

            // Initialize.
            onActionChange();
        }
    }
})();
