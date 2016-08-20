var BrowseSearchHelper = (function() {

    var $form;
    var dateFieldNameToIndex = {
        filter_type: 0,
        year: 1,
        date: 2,
        start_date: 3,
        end_date: 4
    };

    function get$dateField(name) {
        return $form.find(
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

    return {

        init: function(searchFormId) {
            $form = $('#'+searchFormId);

            // Add a handler.
            var $dateFilterTypeField = get$dateField('filter_type');
            $dateFilterTypeField.change(onDateFilterTypeChange);

            // Add datepickers.
            get$dateField('date').datepicker({dateFormat: 'yy-mm-dd'});
            get$dateField('start_date').datepicker({dateFormat: 'yy-mm-dd'});
            get$dateField('end_date').datepicker({dateFormat: 'yy-mm-dd'});

            // Initialize the date field appearance.
            onDateFilterTypeChange();
        }
    }
})();
