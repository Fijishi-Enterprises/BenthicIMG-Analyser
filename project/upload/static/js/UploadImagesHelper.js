/* The following "singleton" design pattern is from
 * http://stackoverflow.com/a/1479341/
 */
var UploadImagesHelper = (function() {

    var $statusDisplay = null;
    var $preUploadSummary = null;
    var $midUploadSummary = null;
    var $filesTable = null;
    var $filesTableContainer = null;
    var $filesTableAutoScrollCheckbox = null;
    var $filesTableAutoScrollCheckboxContainer = null;

    var filesField = null;

    var $uploadStartButton = null;
    var $uploadAbortButton = null;
    var $startAnotherUploadForm = null;
    var $proceedToManageMetadataForm = null;

    var uploadPreviewUrl = null;
    var uploadStartUrl = null;

    var files = [];
    var numErrors = 0;
    var numUploadables = 0;
    var uploadableTotalSize = 0;

    var numUploaded = 0;
    var numUploadSuccesses = 0;
    var numUploadErrors = 0;
    var uploadedTotalSize = 0;
    var uploadedImageIds = null;

    var currentFileIndex = null;
    var uploadXHRObject = null;


    /**
    Makes cssClass the only style class of a particular row (tr element)
    of the files table.
    Pass in '' as the cssClass to just remove the style.

    Assumes we only need up to 1 style on any row at any given time.
    If that assumption is no longer valid, then this function should be
    changed.
    */
    function styleFilesTableRow(rowIndex, cssClass) {
        files[rowIndex].$tableRow.attr('class', cssClass);
    }

    function updateStatus(newStatus) {
        $statusDisplay.empty();

        // Hide and disable both buttons by default. In each case below,
        // specify only what's shown and enabled.
        $uploadStartButton.hide();
        $uploadStartButton.disable();
        $uploadAbortButton.hide();
        $uploadAbortButton.disable();

        if (newStatus === 'no_files') {
            $uploadStartButton.show();
            $statusDisplay.text("No image files selected yet");
        }
        else if (newStatus === 'checking') {
            $uploadStartButton.show();
            $statusDisplay.text("Checking files...");
        }
        else if (newStatus === 'no_uploadables') {
            $uploadStartButton.show();
            $statusDisplay.text("Cannot upload any of these image files");
        }
        else if (newStatus === 'ready') {
            $uploadStartButton.show();
            $uploadStartButton.enable();
            $statusDisplay.text("Ready for upload");
        }
        else if (newStatus === 'uploading') {
            $uploadAbortButton.show();
            $uploadAbortButton.enable();
            $statusDisplay.text("Uploading...");
        }
        else if (newStatus === 'uploaded') {
            $statusDisplay.text("Upload complete");
        }
        else if (newStatus === 'aborted') {
            $statusDisplay.text("Upload aborted");
        }
        else {
            // This should only happen if we don't keep the status strings
            // synced between status get / status set code.
            alert(
                "Error - Invalid status: {0}".format(newStatus) +
                "\nIf the problem persists, please contact the site admins."
            );
        }
    }

    /* Get the file details and display them in the table. */
    function updateFiles() {

        // Clear the table rows
        var i;
        for (i = 0; i < files.length; i++) {
            files[i].$tableRow.remove();
        }
        // Clear the file array
        files.length = 0;

        // No need to do anything more if there are no files anyway.
        if (filesField.files.length === 0) {
            updateStatus('no_files');
            return;
        }

        updateStatus('checking');

        // Re-build the file array.
        // Set the image files as files[0].file, files[1].file, etc.
        for (i = 0; i < filesField.files.length; i++) {
            files.push({'file': filesField.files[i]});
        }

        // Make a table row for each file
        for (i = 0; i < files.length; i++) {

            // Create a table row containing file details
            var $filesTableRow = $("<tr>");

            // Filename, filesize
            $filesTableRow.append($("<td>").text(files[i].file.name));

            var $sizeCell = $("<td>");
            $sizeCell.addClass('size_cell');
            $sizeCell.text(util.filesizeDisplay(files[i].file.size));
            $filesTableRow.append($sizeCell);

            // Filename status, to be filled in with an Ajax response
            var $statusCell = $("<td>");
            $statusCell.addClass('status_cell');
            $filesTableRow.append($statusCell);
            files[i].$statusCell = $statusCell;

            // Add the row to the table
            $filesTable.append($filesTableRow);
            files[i].$tableRow = $filesTableRow;
        }

        // Initialize upload statuses to null
        for (i = 0; i < files.length; i++) {
            files[i].status = null;
        }

        var fileInfoForPreviewQuery = new Array(files.length);
        for (i = 0; i < files.length; i++) {
            fileInfoForPreviewQuery[i] = {
                filename: files[i].file.name,
                size: files[i].file.size
            }
        }

        // Update upload statuses based on the server's info
        $.ajax({
            // URL to make request to
            url: uploadPreviewUrl,
            // Data to send in the request. This is a data structure we'll
            // send as JSON.
            data: {
                file_info: JSON.stringify(fileInfoForPreviewQuery)
            },
            type: 'POST',
            // Callbacks
            success: handleUploadPreviewResponse,
            error: util.handleServerError
        });
    }

    function handleUploadPreviewResponse(response) {
        var statuses = response['statuses'];
        numErrors = 0;
        numUploadables = 0;
        uploadableTotalSize = 0;

        // Update table's status cells
        var i;
        for (i = 0; i < statuses.length; i++) {

            var fileStatus = statuses[i];

            var $statusCell = files[i].$statusCell;
            $statusCell.empty();

            if (fileStatus.hasOwnProperty('error')) {

                if (fileStatus.hasOwnProperty('link')) {
                    $statusCell.append(
                        $("<a>")
                            .text(fileStatus['error'])
                            .attr('href', fileStatus['link'])
                            // Open in new window
                            .attr('target', '_blank')
                    );
                }
                else {
                    $statusCell.text(fileStatus['error']);
                }

                files[i].status = 'error';
                files[i].isUploadable = false;
                numErrors += 1;
                styleFilesTableRow(i, 'preupload_error');
            }
            else {
                $statusCell.text("Ready");

                files[i].status = 'ok';
                files[i].isUploadable = true;
                numUploadables += 1;
                uploadableTotalSize += files[i].file.size;
                styleFilesTableRow(i, '');
            }
        }

        // Update summary above table
        $preUploadSummary.empty();

        var $summaryList = $('<ul>');
        $summaryList.append(
            $('<li>').append(
                $('<strong>').text(
                    "{0} file(s) ({1}) can be uploaded".format(
                        numUploadables,
                        util.filesizeDisplay(uploadableTotalSize)
                    )
                )
            )
        );
        if (numErrors > 0) {
            $summaryList.append(
                $('<li>').text(
                    "{0} file(s) can't be uploaded".format(
                        numErrors
                    )
                )
            );
        }
        $preUploadSummary.append(
            "{0} file(s) total".format(files.length),
            $summaryList
        );

        if (numUploadables <= 0) {
            updateStatus('no_uploadables');
        }
        else {
            updateStatus('ready');
        }

        // Show or hide the files table auto-scroll option
        // depending on whether the table is tall enough to need a scrollbar.
        if ($filesTableContainer[0].scrollHeight >
            $filesTableContainer[0].clientHeight) {
            // There is overflow in the files table container, such that
            // it has a scrollbar.
            $filesTableAutoScrollCheckboxContainer.show();
        }
        else {
            // No scrollbar.
            $filesTableAutoScrollCheckboxContainer.hide();
        }
    }

    function startUpload() {
        // Disable all form fields and buttons on the page.
        $(filesField).prop('disabled', true);

        // Initialize the upload progress stats.
        numUploaded = 0;
        numUploadSuccesses = 0;
        numUploadErrors = 0;
        uploadedTotalSize = 0;
        updateMidUploadSummary();

        uploadedImageIds = [];

        // Warn the user if they're trying to
        // leave the page during the upload.
        util.pageLeaveWarningEnable("The upload is still going.");

        updateStatus('uploading');

        // Finally, upload the first file.
        currentFileIndex = 0;
        uploadFile();
    }

    /* Callback after one image's upload and processing are done. */
    function handleUploadResponse(response) {

        // Update the table with the upload status from the server.
        var $statusCell = files[currentFileIndex].$statusCell;
        $statusCell.empty();

        if (response.hasOwnProperty('error')) {
            $statusCell.text(response['error']);
            styleFilesTableRow(currentFileIndex, 'upload_error');
            numUploadErrors++;
        }
        else {
            $statusCell.append(
                $("<a>")
                    .text("Uploaded")
                    .attr('href', response['link'])
                    // Open in new window
                    .attr('target', '_blank')
            );
            styleFilesTableRow(currentFileIndex, 'uploaded');
            numUploadSuccesses++;
            uploadedImageIds.push(response['image_id']);
        }
        numUploaded++;
        uploadedTotalSize += files[currentFileIndex].file.size;

        updateMidUploadSummary();

        // Find the next file to upload, if any, and upload it.
        currentFileIndex++;
        uploadFile();
    }

    /* Find a file to upload, starting from the current currentFileIndex.
     * If the current file is not uploadable, increment the currentFileIndex
     * and try the next file.  Once an uploadable file is found, begin
     * uploading that file. */
    function uploadFile() {
        while (currentFileIndex < files.length) {

            if (files[currentFileIndex].isUploadable) {
                // An uploadable file was found, so upload it.

                // https://developer.mozilla.org/en-US/docs/Web/API/FormData/Using_FormData_Objects
                var formData = new FormData();
                // Add the file as 'file' so that it can be validated
                // on the server side with a form field named 'file'.
                formData.append('file', files[currentFileIndex].file);

                uploadXHRObject = $.ajax({
                    // URL to make request to
                    url: uploadStartUrl,
                    // Data to send in the request
                    data: formData,
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
                    success: handleUploadResponse,
                    error: util.handleServerError
                });

                // In the files table, update the status for that file.
                var $statusCell = files[currentFileIndex].$statusCell;
                $statusCell.empty();
                styleFilesTableRow(currentFileIndex, 'uploading');
                $statusCell.text("Uploading...");

                if ($filesTableAutoScrollCheckbox.prop('checked')) {
                    // Scroll the upload table's window to the file
                    // that's being uploaded.
                    // Specifically, scroll the file to the
                    // middle of the table view.
                    var scrollRowToTop = files[currentFileIndex].$tableRow[0].offsetTop;
                    var tableContainerHalfMaxHeight = parseInt($filesTableContainer.css('max-height')) / 2;
                    var scrollRowToMiddle = Math.max(scrollRowToTop - tableContainerHalfMaxHeight, 0);
                    $filesTableContainer.scrollTop(scrollRowToMiddle);
                }

                return;
            }

            // No uploadable file was found yet; keep looking.
            currentFileIndex++;
        }

        // Reached the end of the files array.
        updateStatus('uploaded');
        postUploadCleanup();

        // Set the uploaded image Ids in the proceed-to-manage-metadata form.
        var commaSeparatedImageIds = uploadedImageIds.join();
        $('input#id_specify_str').val(commaSeparatedImageIds);

        // Show the buttons for the user's next step.
        $startAnotherUploadForm.show();
        $proceedToManageMetadataForm.show();
    }

    function postUploadCleanup() {
        uploadXHRObject = null;
        util.pageLeaveWarningDisable();
    }

    function updateMidUploadSummary() {
        $midUploadSummary.empty();

        var summaryTextLines = [];

        summaryTextLines.push($('<strong>').text("Uploaded: {0} of {1} ({2} of {3}, {4}%)".format(
            numUploaded,
            numUploadables,
            util.filesizeDisplay(uploadedTotalSize),
            util.filesizeDisplay(uploadableTotalSize),
            ((uploadedTotalSize/uploadableTotalSize)*100).toFixed(1)  // Percentage with 1 decimal place
        )));

        if (numUploadErrors > 0) {
            summaryTextLines.push("Upload successes: {0} of {1}".format(numUploadSuccesses, numUploaded));
            summaryTextLines.push("Upload errors: {0} of {1}".format(numUploadErrors, numUploaded));
        }

        var i;
        for (i = 0; i < summaryTextLines.length; i++) {
            // If not the first line, append a <br> first.
            // That way, the lines are separated by linebreaks.
            if (i > 0) {
                $midUploadSummary.append('<br>');
            }

            $midUploadSummary.append(summaryTextLines[i]);
        }
    }

    /**
    Abort the Ajax upload.

    - Depending on the timing of clicking Abort, a file may finish
    uploading and proceed with processing on the server, without a result
    being received by the client. This is probably undesired behavior,
    but there's not much that can be done about this.

    - There should be no concurrency issues, because Javascript is single
    threaded, and event handling code is guaranteed to complete before the
    invocation of an AJAX callback or a later event's callback. At least
    in the absence of Web Workers.
    http://stackoverflow.com/questions/9999056/
    */
    function abortUpload() {
        var confirmation = window.confirm(
            "Are you sure you want to abort the upload?");

        if (confirmation) {
            if (uploadXHRObject !== null) {
                uploadXHRObject.abort();
                updateStatus('aborted');
                postUploadCleanup();
            }
            // Else, the upload finished before the user could confirm the
            // abort (so there's nothing to abort anymore).  This could
            // happen in Firefox, where scripts don't stop even when a
            // confirmation dialog is showing.
        }
    }


    /* Public methods.
     * These are the only methods that need to be referred to as
     * UploadImagesHelper.methodname. */
    return {

        /* Initialize the page. */
        init: function(params){

            // Get the parameters.
            uploadPreviewUrl = params['uploadPreviewUrl'];
            uploadStartUrl = params['uploadStartUrl'];

            // Upload status summary elements.
            $preUploadSummary = $('#pre_upload_summary');
            $midUploadSummary = $('#mid_upload_summary');

            // The upload file table.
            $filesTable = $('table#files_table');
            // And its container element.
            $filesTableContainer = $('#files_table_container');
            // The checkbox to enable/disable auto-scrolling
            // of the files table.
            $filesTableAutoScrollCheckbox = $('input#files_table_auto_scroll_checkbox');
            // And its container element.
            $filesTableAutoScrollCheckboxContainer = $('#files_table_auto_scroll_checkbox_container');

            // Field elements.
            filesField = $('#id_files')[0];

            // Button elements.
            $uploadStartButton = $('#id_upload_submit');
            $uploadAbortButton = $('#id_upload_abort_button');
            $startAnotherUploadForm = $('#id_start_another_upload_form');
            $proceedToManageMetadataForm = $('#id_proceed_to_manage_metadata_form');

            $statusDisplay = $('#status_display');


            // Hide the after-upload buttons for now
            $startAnotherUploadForm.hide();
            $proceedToManageMetadataForm.hide();

            // Handlers.
            $(filesField).change( function(){
                updateFiles();
            });
            $uploadStartButton.click(startUpload);
            $uploadAbortButton.click(abortUpload);

            // Initialize the page properly regardless of whether
            // we load the page straight (no files initially) or
            // refresh the page (browser may keep previous file field value).
            updateFiles();
        }
    }
})();
