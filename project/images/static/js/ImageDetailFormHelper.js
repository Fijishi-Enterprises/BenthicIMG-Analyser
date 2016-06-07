var ImageDetailFormHelper = {

    init: function() {
        // Add onchange handler to each location-value dropdown field
        for (var i = 1; $("#id_aux" + i).length != 0; i++) {

            var auxFieldJQ = $("#id_aux" + i);

            // Show/hide this value's Other field right now
            ImageDetailFormHelper.showOrHideOtherField(auxFieldJQ[0]);
            
            // Show/hide this value's Other field when the dropdown value changes
            auxFieldJQ.change( function() {
                ImageDetailFormHelper.showOrHideOtherField(this);
            });
        }
    },


    showOrHideOtherField: function(auxField) {
        var otherFieldWrapperJQ = $("#" + auxField.id + "_other_wrapper");
        if (auxField.value === 'Other') {
            otherFieldWrapperJQ.show();
        }
        else {
            otherFieldWrapperJQ.hide();
        }
    }
};

util.addLoadEvent(ImageDetailFormHelper.init);
