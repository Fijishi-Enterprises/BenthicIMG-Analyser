/* The following "singleton" design pattern is from
 * http://stackoverflow.com/a/1479341/
 */
var LabelNew = (function() {

    var afterLabelCreated = null;

    var $formStatus = null;
    var $form = null;


    function submitForm() {
        $.ajax({
            // URL to make request to
            url: $form.attr('action'),
            // Data to send in the request;
            // FormData can handle this even when files are included
            data: new FormData($form[0]),
            // Don't let jQuery auto-set the Content-Type header
            // if we're using FormData
            // http://stackoverflow.com/a/5976031/
            contentType: false,
            // Don't let jQuery attempt to convert the FormData
            // to a string, as it will fail
            // http://stackoverflow.com/a/5976031/
            processData: false,
            type: 'POST',
            // Callbacks
            success: handleSubmitResponse,
            error: util.handleServerError
        });
    }


    function handleSubmitResponse(response) {
        $formStatus.empty();

        if (response['error']) {
            // Response is JSON which contains the error
            // (which can be just text, or can contain safe HTML)
            $formStatus.append($('<span>' + response['error'] + '</span>'));
            return;
        }

        // HTML response with button/dialog elements for the new label
        $formStatus.text("Label successfully created.");
        afterLabelCreated(response);
        // TODO: Clear the form?
    }


    /* Public methods.
     * These are the only methods that need to be referred to as
     * <SingletonClassName>.<methodName>. */
    return {
        init: function(params) {
            // afterLabelCreated is a function that should take a label id
            // (a Number) as its only argument.
            afterLabelCreated = params['afterLabelCreated'];

            $formStatus = $('#label-form-status');

            $form = $('#label-form');
            $form.submit(function() {
                try {
                    submitForm();
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
        }
    }
})();
