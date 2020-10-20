var ImageSearchHelper = (function() {

    var searchForm;

    function showField(field) {
        field.style.display = 'inline-block';
    }

    function hideField(field) {
        field.style.display = 'none';
    }

    function onControlFieldChange(
            controlFieldName, conditionallyVisibleFieldName, requiredValue) {
        var controlField = searchForm.querySelector(
            '[name="{0}"]'.format(controlFieldName));
        var conditionallyVisibleField = searchForm.querySelector(
            '[name="{0}"]'.format(conditionallyVisibleFieldName));

        if (controlField.value === requiredValue) {
            showField(conditionallyVisibleField);
        }
        else {
            hideField(conditionallyVisibleField);
        }
    }

    return {
        init: function(params) {
            searchForm = document.getElementById('search-form');

            var conditionallyVisibleFields = searchForm.querySelectorAll(
                '[data-visibility-condition]')

            // Example conditions: `0=annotation_tool` `2=date_range`
            var conditionRegex = /^(\d+)=([^=]+)$/;
            // Example subfield name: `date-filter-0`
            var subFieldNameRegex = /^(.+_)\d+$/;

            conditionallyVisibleFields.forEach(function(field) {
                var condition =
                    field.attributes['data-visibility-condition'].value;
                var match = condition.match(conditionRegex);
                var index = match[1];
                var value = match[2];
                var subFieldName = field.attributes['name'].value;
                var subFieldNamePrefix = subFieldName.match(
                    subFieldNameRegex)[1];
                var controlFieldName = subFieldNamePrefix + index.toString();
                var controlField = searchForm.querySelector(
                    '[name="{0}"]'.format(controlFieldName));

                // When the control field changes, update visibility of the
                // conditionally visible field.
                var onControlFieldChangeCurried = onControlFieldChange.curry(
                    controlFieldName, subFieldName, value)
                controlField.addEventListener(
                    'change', onControlFieldChangeCurried);

                // Initialize field visibility.
                onControlFieldChangeCurried();
            });

            // Add datepickers.
            $('input[data-has-datepicker]').datepicker(
                {dateFormat: 'yy-mm-dd'});
        }
    }
})();
