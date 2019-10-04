/* The following "singleton" design pattern is from
 * http://stackoverflow.com/a/1479341/
 */
var LabelsetImport = (function() {

    var $statusDisplay = null;
    var $statusDetail = null;
    var $previewTableContainer = null;

    var $csvForm = null;
    var csvFileField = null;
    var $csvFileError = null;
    var $previewTable = null;
    var $previewDetail = null;

    var $uploadStartButton = null;

    var uploadPreviewUrl = null;
    var uploadStartUrl = null;


    function updateStatus(newStatus) {
        $statusDisplay.empty();

        // Update the upload start button.
        if (newStatus === 'no_file') {
            $uploadStartButton.disable();
            $statusDisplay.text("CSV file not selected yet");
            $statusDetail.empty();
        }
        else if (newStatus === 'processing') {
            $uploadStartButton.disable();
            $statusDisplay.text("Processing CSV file...");
            $statusDetail.empty();
        }
        else if (newStatus === 'preview_error') {
            $uploadStartButton.disable();
            $statusDisplay.text("Error reading the CSV file");
            $statusDetail.empty();

            // Fill $statusDetail with the error HTML
            $statusDetail.append($csvFileError);
        }
        else if (newStatus === 'ready') {
            $uploadStartButton.enable();
            $statusDisplay.text(
                "Confirm the new labelset below" +
                " and click 'Save labelset'");

            $statusDetail.empty();
            $statusDetail.append($previewDetail);
        }
        else if (newStatus === 'saving') {
            $uploadStartButton.disable();
            $statusDisplay.text("Saving labelset...");
            // Retain previous status detail
        }
        else if (newStatus === 'save_error') {
            $uploadStartButton.disable();
            $statusDisplay.text("Error saving the labelset");
            $statusDetail.empty();

            // Fill $statusDetail with the error HTML
            $statusDetail.append($csvFileError);
        }
        else if (newStatus === 'saved') {
            $uploadStartButton.disable();
            $statusDisplay.text("Labelset saved");
            // Retain previous status detail
        }
        else {
            // This should only happen if we don't keep the status strings
            // synced between status get / status set code.
            alert(
                "Error - Invalid status: {0}".format(newStatus) +
                "\nIf the problem persists, please let us know on the forum."
            );
        }
    }

    function updatePreviewTable() {
        $previewTableContainer.empty();

        if ($previewTable === null) {
            return;
        }

        $previewTableContainer.append($previewTable);
    }

    function updateUploadPreview() {
        $previewTable = null;

        if (csvFileField.files.length === 0) {
            // No CSV file.
            updateStatus('no_file');
            updatePreviewTable();
            return;
        }

        updateStatus('processing');
        updatePreviewTable();

        $.ajax({
            // URL to make request to
            url: uploadPreviewUrl,
            // Data to send in the request
            // https://developer.mozilla.org/en-US/docs/Web/API/FormData/Using_FormData_Objects
            data: new FormData($csvForm[0]),
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
            success: handleUploadPreviewResponse,
            error: util.handleServerError
        });
    }

    function handleUploadPreviewResponse(response) {
        if (response['error']) {
            $csvFileError = $('<span>' + response['error'] + '</span>');
            updateStatus('preview_error');
        }
        else {
            $previewTable = $(response['previewTable']);
            $previewDetail = $(
                '<span>' + response['previewDetail'] + '</span>');
            updateStatus('ready');
        }
        updatePreviewTable();
    }

    function startUpload() {
        updateStatus('saving');

        // Warn the user if they're trying to
        // leave the page during the save.
        util.pageLeaveWarningEnable("Labelset entries are still being saved.");

        // Start the upload.
        $.ajax({
            // URL to make request to
            url: uploadStartUrl,
            type: 'POST',
            // Callbacks
            success: handleUploadResponse,
            error: util.handleServerError
        });
    }

    /* Callback after the Ajax response is received, indicating that
     * the server upload and processing are done. */
    function handleUploadResponse(response) {
        if (response['error']) {
            $csvFileError = $('<span>' + response['error'] + '</span>');
            updateStatus('save_error');
        }
        else {
            updateStatus('saved');
        }

        util.pageLeaveWarningDisable();
    }


    /* Public methods.
     * These are the only methods that need to be referred to as
     * <SingletonClassName>.<methodName>. */
    return {

        /* Initialize the upload form. */
        initForm: function(params){

            // Get the parameters.
            uploadPreviewUrl = params['uploadPreviewUrl'];
            uploadStartUrl = params['uploadStartUrl'];

            // Upload status elements.
            $statusDisplay = $('#status_display');
            $statusDetail = $('#status_detail');

            // Preview table's container element.
            $previewTableContainer = $('#preview_table_container');

            // Form and field elements.
            $csvForm = $('#csv_form');
            csvFileField = $('#id_csv_file')[0];

            // Button elements.
            $uploadStartButton = $('#id_upload_submit');


            // Handlers.
            $(csvFileField).change(function() {
                updateUploadPreview();
            });
            $uploadStartButton.click(function() {
                startUpload();
            });

            // Initialize the page properly regardless of whether
            // we load the page straight (no files initially) or
            // refresh the page (browser may keep previous file field value).
            updateUploadPreview();
        }
    }
})();
