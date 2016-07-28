/* The following "singleton" design pattern is from
 * http://stackoverflow.com/a/1479341/
 */
var UploadMetadataHelper = (function() {

    var $statusDisplay = null;
    var $statusDetail = null;
    var $previewTable = null;
    var $previewTableContainer = null;

    var $csvForm = null;
    var csvFileField = null;
    var csvFileStatus = null;
    var csvFileError = null;
    var previewTableContent = null;
    var previewDetails = null;

    var $csvRefreshButton = null;
    var $uploadStartButton = null;

    var uploadPreviewUrl = null;
    var uploadStartUrl = null;


    function updateStatus() {
        var messageLines;
        var i;

        $statusDisplay.empty();

        // Update the upload start button.
        if (csvFileField.files.length === 0) {
            $uploadStartButton.disable();
            $statusDisplay.text("CSV file not selected yet");
            $statusDetail.empty();
        }
        else if (csvFileStatus === 'processing') {
            $uploadStartButton.disable();
            $statusDisplay.text("Processing CSV file...");
            $statusDetail.empty();
        }
        else if (csvFileStatus === 'preview_error') {
            $uploadStartButton.disable();
            $statusDisplay.text("Error reading the CSV file");
            $statusDetail.empty();

            // Fill $statusDetail with the error message,
            // which may span multiple lines
            messageLines = csvFileError.split('\n');
            for (i = 0; i < messageLines.length; i++) {
                $statusDetail.append(messageLines[i]);

                if (i < messageLines.length-1) {
                    $statusDetail.append($('<br>'));
                }
            }
        }
        else if (csvFileStatus === 'ready') {
            $uploadStartButton.enable();
            $statusDisplay.text(
                "Metadata OK; confirm below and click 'Save metadata'");

            $statusDetail.empty();
            $statusDetail.append(
                "{0} images found".format(previewDetails['numImages']));

            if (previewDetails['numFieldsReplaced'] > 0) {
                $statusDetail.append(
                    $('<br>'),
                    $('<span class="old-metadata-value">').append(
                        "{0} non-blank fields to be replaced".format(
                        previewDetails['numFieldsReplaced']))
                );
            }
        }
        else if (csvFileStatus === 'saving') {
            $uploadStartButton.disable();
            $statusDisplay.text("Saving metadata...");
            // Retain previous status detail
        }
        else if (csvFileStatus === 'save_error') {
            $uploadStartButton.disable();
            $statusDisplay.text("Error saving the CSV file; no metadata saved");
            $statusDetail.empty();

            // Fill $statusDetail with the error message,
            // which may span multiple lines
            messageLines = csvFileError.split('\n');
            for (i = 0; i < messageLines.length; i++) {
                $statusDetail.append(messageLines[i]);

                if (i < messageLines.length-1) {
                    $statusDetail.append($('<br>'));
                }
            }
        }
        else if (csvFileStatus === 'saved') {
            $uploadStartButton.disable();
            $statusDisplay.text("Metadata saved");
            // Retain previous status detail
        }
        else {
            // This should only happen if we don't keep the status strings
            // synced between status get / status set code.
            alert(
                "Error - Invalid status: {0}".format(csvFileStatus) +
                "\nIf the problem persists, please contact the site admins."
            );
        }
    }

    function updatePreviewTable() {
        $previewTable.empty();

        if (previewTableContent === null) {
            return;
        }

        var $firstRow = $('<tr>');
        var tableHeaders = previewTableContent[0];
        var i, j;

        // Header row
        for (i = 0; i < tableHeaders.length; i++) {
            $firstRow.append($('<th>').text(tableHeaders[i]));
        }
        $previewTable.append($firstRow);
        // One row for each image specified in the CSV
        for (i = 1; i < previewTableContent.length; i++) {
            var rowContent = previewTableContent[i];
            var $row = $('<tr>');

            for (j = 0; j < rowContent.length; j++) {
                var cellContent = rowContent[j];
                if (cellContent instanceof Array) {
                    $row.append(
                        $('<td>').append(
                            // New value
                            cellContent[0],
                            // Line break
                            $('<br>'),
                            // Old value, styled differently
                            $('<span class="old-metadata-value">').append(
                                cellContent[1]
                            )
                        )
                    );
                }
                else {
                    $row.append($('<td>').text(cellContent));
                }
            }
            $previewTable.append($row);
        }
    }

    function updateUploadPreview() {
        previewTableContent = null;

        if (csvFileField.files.length === 0) {
            // No CSV file.
            updateStatus();
            updatePreviewTable();
            return;
        }

        csvFileStatus = 'processing';
        updateStatus();
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
            csvFileStatus = 'preview_error';
            csvFileError = response['error'];
        }
        else {
            csvFileStatus = 'ready';
            previewTableContent = response['previewTable'];
            previewDetails = response['previewDetails'];
        }
        updateStatus();
        updatePreviewTable();
    }

    function startUpload() {
        csvFileStatus = 'saving';
        updateStatus();

        // Warn the user if they're trying to
        // leave the page during the save.
        util.pageLeaveWarningEnable("Metadata is still being saved.");

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
        if (response.error) {
            csvFileStatus = 'save_error';
            csvFileError = response.error;
        }
        else {
            csvFileStatus = 'saved';
        }
        updateStatus();

        util.pageLeaveWarningDisable();
    }


    /* Public methods.
     * These are the only methods that need to be referred to as
     * UploadMetadataHelper.methodname. */
    return {

        /* Initialize the upload form. */
        initForm: function(params){

            // Get the parameters.
            uploadPreviewUrl = params['uploadPreviewUrl'];
            uploadStartUrl = params['uploadStartUrl'];

            // Upload status elements.
            $statusDisplay = $('#status_display');
            $statusDetail = $('#status_detail');

            // Preview table.
            $previewTable = $('table#preview_table');
            // And its container element.
            $previewTableContainer = $('#preview_table_container');

            // Form and field elements.
            $csvForm = $('#csv_form');
            csvFileField = $('#id_csv_file')[0];

            // Button elements.
            $csvRefreshButton = $('#csv_refresh_button');
            $uploadStartButton = $('#id_upload_submit');


            // Handlers.
            $(csvFileField).change(function() {
                updateUploadPreview();
            });
            $csvRefreshButton.click(function() {
                updateUploadPreview();
            });
            $uploadStartButton.click(function() {
                startUpload();
            });

            updateStatus();
        }
    }
})();
