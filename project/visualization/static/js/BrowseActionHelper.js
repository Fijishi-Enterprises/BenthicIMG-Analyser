var BrowseActionHelper = (function() {

    var pageImageIds;
    var links;

    var $actionBox;
    var $actionForms;
    var $currentActionForm;
    var $imageSelectFieldContainer;
    var $actionSubmitButton;

    var $actionSelectField;
    var $exportTypeField;
    var $imageSelectTypeField;

    function onActionChange() {
        var action = $actionSelectField.val();
        var export_type = $exportTypeField.val();
        var image_select_type = $imageSelectTypeField.val();

        // Show the 'specifics' element for only the selected action
        $('#action_box_annotate_specifics').hide();
        $('#action_box_export_specifics').hide();
        $('#action_box_delete_specifics').hide();
        $('#action_box_{0}_specifics'.format(action)).show();

        // Show only the relevant action form
        // TODO: Consider also disabling buttons etc. of hidden forms.
        $actionForms.hide();

        if (action === 'annotate' && image_select_type === 'all') {
            $currentActionForm = $('#annotate-all-form');
        }
        else if (action === 'annotate' && image_select_type === 'selected') {
            $currentActionForm = $('#annotate-selected-form');
        }
        else if (action === 'export' && export_type === 'metadata') {
            $currentActionForm = $('#export-metadata-form');
        }
        else if (action === 'export' && export_type === 'annotations_simple') {
            $currentActionForm = $('#export-annotations-simple-form');
        }
        else if (action === 'export' && export_type === 'annotations_full') {
            $currentActionForm = $('#export-annotations-full-form');
        }
        else if (action === 'export' && export_type === 'annotations_cpc') {
            $currentActionForm = $('#export-annotations-cpc-form');
        }
        else if (action === 'export' && export_type === 'image_covers') {
            $currentActionForm = $('#export-image-covers-form');
        }
        else if (action === 'delete') {
            $currentActionForm = $('#delete-form');
        }

        $currentActionForm.show();
        $imageSelectFieldContainer =
            $currentActionForm.find('.image-select-field-container');
        $actionSubmitButton =
            $currentActionForm.find('button.submit');
    }

    function addImageSelectField(name, value) {
        // Add as hidden fields because the user doesn't have to
        // interact with them.
        $imageSelectFieldContainer.append($('<input/>', {
            type: 'hidden',
            name: name,
            value: value
        }));
    }
    function setActionFormUrl(url) {
        $currentActionForm.attr('action', url);
    }

    function actionSubmit() {
        // Clear image select fields from any previous submit attempts.
        $currentActionForm.find('.image-select-field-container').empty();

        var action = $actionSelectField.val();
        var imageSelectType = $imageSelectTypeField.val();

        // Image-select fields must be passed differently according to
        // the user's chosen image select type (all images, or only
        // selected images). We implement this by adding the fields to the
        // relevant action form via Javascript, here in the submit button
        // handler.
        var imageSelectArgs = {};
        if (imageSelectType === 'all') {
            $('#previous-image-form-fields').find('input').each(
                function () { imageSelectArgs[this.name] = this.value; }
            );
        }
        else if (imageSelectType === 'selected') {
            imageSelectArgs['image_form_type'] = 'ids';
            imageSelectArgs['ids'] = pageImageIds.toString();
        }

        if (action === 'delete') {
            if (!areYouSureDelete()) { return; }
            deleteImages(imageSelectArgs);
        }
        else if (action === 'export'
         && $exportTypeField.val() === 'annotations_cpc') {
            exportAnnotationsCPC(imageSelectArgs);
        }
        else {
            for (var key in imageSelectArgs) {
                if (!imageSelectArgs.hasOwnProperty(key)) { continue; }
                addImageSelectField(key, imageSelectArgs[key]);
            }
            $currentActionForm.submit();
        }
    }

    function areYouSureDelete() {
        var userInput = window.prompt(
            "Are you sure you want to delete these images?" +
            " You won't be able to undo this." +
            " Type \"delete\" if you're sure.");
        return (userInput === "delete");
    }
    function deleteImages(imageSelectArgs) {
        // This will run after deletion is complete.
        var callback = function(response) {
            if (response['error']) {
                // TODO: Can we do better than an alert? Since we have more
                // flexibility over individual action forms' layouts now.
                alert("Error: " + response['error']);
                $actionSubmitButton.enable();
                $actionSubmitButton.text("Go");
                return;
            }

            // Re-fetch the current browse page.
            $('#previous-image-form-fields').find('input').each(
                function () { addImageSelectField(this.name, this.value); }
            );
            $currentActionForm.submit();
        };

        // Delete images, then once it's done, run the callback.
        //
        // Since the first step is Ajax, let the user know what's going
        // on, and disable the button to prevent double submission.
        // TODO: Also consider disabling all the select fields. Switching
        // forms before the callback happens could get unintuitive
        // behavior.
        $actionSubmitButton.disable();
        $actionSubmitButton.text("Deleting...");
        $.post(links['delete'], imageSelectArgs, callback);
        window.seleniumDebugDeleteTriggered = true;
    }

    function exportAnnotationsCPC(imageSelectArgs) {
        // This will run after CPCs are built.
        var callback = function(response) {
            if (response['error']) {
                // TODO: Can we do better than an alert? Since we have more
                // flexibility over individual action forms' layouts now.
                alert("Error: " + response['error']);
                $actionSubmitButton.enable();
                $actionSubmitButton.text("Go");
                return;
            }

            // Start the download.
            $currentActionForm.submit();

            $actionSubmitButton.enable();
            $actionSubmitButton.text("Go");
        };

        // Build CPCs for export, then once it's done, run the callback
        // to start the download.
        //
        // Since the first step is Ajax, let the user know what's going
        // on, and disable the button to prevent double submission.
        $actionSubmitButton.disable();
        $actionSubmitButton.text("Getting annotations...");
        // postArgs will include image-select and CPC-prefs arguments.
        var postArgs = Object.assign(imageSelectArgs);
        $('#cpc-prefs-fields-container').find('input').each(function(){
            postArgs[this.name] = this.value;
        });
        $.post(
            links['export_annotations_cpc_create_ajax'],
            postArgs, callback
        );
    }

    return {
        init: function(params) {
            pageImageIds = params['pageImageIds'];
            links = params['links'];

            $actionBox = $('#action-box');
            $actionForms = $actionBox.find('form');

            // Grab select fields and add handlers.
            $actionSelectField =
                $actionBox.find('select[name=browse_action]');
            $actionSelectField.change(onActionChange);
            $exportTypeField =
                $actionBox.find('select[name=export_type]');
            $exportTypeField.change(onActionChange);
            $imageSelectTypeField =
                $actionBox.find('select[name=image_select_type]');
            $imageSelectTypeField.change(onActionChange);

            // Add submit button handlers.
            $actionForms.find('button.submit').click(actionSubmit);

            // Initialize.
            onActionChange();
        }
    }
})();
