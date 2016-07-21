/* The following "singleton" design pattern is from
 * http://stackoverflow.com/a/1479341/
 *
 * Main update functions called in event handling code:
 * updateFilesTable
 *
 * Typically, any event handling function will only need to call
 * that function.
 */
var ImageUploadFormHelper = (function() {

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

    var $uploadStartInfo = null;

    var $pointGenText = null;

    var uploadPreviewUrl = null;
    var uploadStartUrl = null;

    var files = [];
    var numDupes = 0;
    var numUploadables = 0;
    var uploadableTotalSize = 0;

    var numUploaded = 0;
    var numUploadSuccesses = 0;
    var numUploadErrors = 0;
    var uploadedTotalSize = 0;
    var uploadedImageIds = null;

    var currentFileIndex = null;
    var uploadXHRObject = null;


    /* Makes cssClass the only style class of a particular row (tr element)
     * of the files table.
     * Pass in '' as the cssClass to just remove the style.
     *
     * Assumes we only need up to 1 style on any row at any given time.
     * If that assumption is no longer valid, then this function should be
     * changed. */
    function styleFilesTableRow(rowIndex, cssClass) {
        files[rowIndex].$tableRow.attr('class', cssClass);
    }

    function updateFormFields() {
        // Update the upload start button.
        if (files.length === 0) {
            // No image files
            $uploadStartButton.disable();
            $uploadStartInfo.text("No image files selected yet");
        }
        else if (numUploadables === 0) {
            // No uploadable image files
            $uploadStartButton.disable();
            $uploadStartInfo.text("Cannot upload any of these image files");
        }
        else {
            // Uploadable image files present
            $uploadStartButton.enable();
            $uploadStartInfo.text("Ready for upload");
        }

        // Show or hide the files list auto-scroll option
        // depending on whether it's relevant or not.
        if ($filesTableContainer[0].scrollHeight > $filesTableContainer[0].clientHeight) {
            // There is overflow in the files table container, such that
            // it has a scrollbar. So the auto-scroll option is relevant.
            $filesTableAutoScrollCheckboxContainer.show();
        }
        else {
            // No scrollbar. The auto-scroll option is not relevant.
            $filesTableAutoScrollCheckboxContainer.hide();
        }
    }

    function updateFilesTable() {
        // Are the files uploadable or not?
        updateUploadability();

        // Update table row styles according to file status
        updatePreUploadStyle();

        // Update the summary text above the files table
        updatePreUploadSummary();

        // Update the form fields. For example, depending on the file statuses,
        // the ability to click the start upload button could change.
        updateFormFields();
    }

    /* Update the isUploadable status of each file. */
    function updateUploadability() {
        numUploadables = 0;
        uploadableTotalSize = 0;

        var i;
        for (i = 0; i < files.length; i++) {
            // Uploadable: ok, possible dupe
            // Not uploadable: error, null(uninitialized status)
            var isUploadable = (files[i].status === 'ok');

            if (isUploadable) {
                numUploadables++;
                uploadableTotalSize += files[i].file.size;
            }

            files[i].isUploadable = isUploadable;
        }
    }

    /* Update the files table rows' styles according to the file statuses. */
    function updatePreUploadStyle() {
        var i;
        for (i = 0; i < files.length; i++) {
            if (files[i].status === 'ok') {
                styleFilesTableRow(i, '');
            }
            else if (files[i].status === 'dupe') {
                styleFilesTableRow(i, 'preupload_dupe');
            }
            else {
                // Perhaps no status is set yet. As far as this function is
                // concerned, that's fine; just use the default style.
                styleFilesTableRow(i, '');
            }
        }
    }

    /* Update the summary text above the files table. */
    function updatePreUploadSummary() {
        $preUploadSummary.empty();

        if (files.length === 0) {
            return;
        }

        $preUploadSummary.text(files.length + " file(s) total");

        var $summaryList = $('<ul>');
        $preUploadSummary.append($summaryList);

        $summaryList.append(
            $('<li>').append(
                $('<strong>').text(
                    "{0} file(s) ({1}) are uploadable images".format(
                        numUploadables,
                        util.filesizeDisplay(uploadableTotalSize)
                    )
                )
            )
        );
        if (numDupes > 0) {
            $summaryList.append(
                $('<li>').text(
                    "{0} image(s) have names matching existing images".format(
                        numDupes
                    )
                )
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
            return;
        }

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

        var filenameList = new Array(files.length);
        for (i = 0; i < files.length; i++) {
            filenameList[i] = files[i].file.name;
        }

        // Ask the server (via Ajax) about the filenames: are they in the
        // right format (if applicable)? Are they duplicates of files on
        // the server?
        $.ajax({
            // Data to send in the request
            data: {
                filenames: filenameList
            },

            // Callback on successful response
            success: filenameStatusAjaxResponseHandler,

            type: 'POST',

            // URL to make request to
            url: uploadPreviewUrl
        });
    }

    function filenameStatusAjaxResponseHandler(response) {
        updateFilenameStatuses(response.statusList);
    }

    function updateFilenameStatuses(statusList) {
        numDupes = 0;

        var i;
        for (i = 0; i < statusList.length; i++) {

            var $statusCell = files[i].$statusCell;
            $statusCell.empty();

            var statusStr = statusList[i].status;

            if (statusStr === 'dupe') {

                var linkToDupe = $("<a>").text("Duplicate name");
                // Link to the image's page
                linkToDupe.attr('href', statusList[i].url);
                // Open in new window
                linkToDupe.attr('target', '_blank');
                linkToDupe.attr('title', statusList[i].title);
                $statusCell.append(linkToDupe);

                numDupes += 1;
            }
            else if (statusStr === 'ok') {
                $statusCell.text("Ready");
            }
            else {
                // This'll only happen if we don't keep the status strings
                // synced between server code and client code.
                console.log("Invalid status: " + statusStr);
            }

            files[i].status = statusStr;
            if (statusList[i].hasOwnProperty('metadataKey')) {
                files[i].metadataKey = statusList[i].metadataKey;
            }
        }

        updateFilesTable();
    }

    function startAjaxImageUpload() {
        // Disable all form fields and buttons on the page.
        $(filesField).prop('disabled', true);

        $uploadStartButton.hideAndDisable();
        $uploadStartInfo.text("Uploading...");

        $uploadAbortButton.prop('disabled', false);
        $uploadAbortButton.show();

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

        // Finally, upload the first file.
        currentFileIndex = 0;
        uploadFile();
    }

    /* Callback after the Ajax response is received, indicating that
     * the server upload and processing are done. */
    function ajaxUploadHandleResponse(response) {

        // Update the table with the upload status from the server.
        var $statusCell = files[currentFileIndex].$statusCell;
        $statusCell.empty();

        if (response.link !== null) {
            var linkToImage = $('<a>').text(response.message);
            linkToImage.attr('href', response.link);
            linkToImage.attr('target', '_blank');
            linkToImage.attr('title', response.title);
            $statusCell.append(linkToImage);
        }
        else {
            $statusCell.text(response.message);
        }

        if (response.status === 'ok') {
            styleFilesTableRow(currentFileIndex, 'uploaded');
            numUploadSuccesses++;
            uploadedImageIds.push(response.image_id);
        }
        else {  // 'error'
            styleFilesTableRow(currentFileIndex, 'upload_error');
            numUploadErrors++;
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
                    // Callback on successful response
                    success: ajaxUploadHandleResponse
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
        $uploadStartInfo.text("Upload Complete");

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

        $uploadAbortButton.hide();
        $uploadAbortButton.prop('disabled', true);

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
    function abortAjaxUpload() {
        var confirmation = window.confirm(
            "Are you sure you want to abort the upload?");

        if (confirmation) {
            if (uploadXHRObject !== null) {
                uploadXHRObject.abort();
                $uploadStartInfo.text("Upload aborted");
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
     * ImageUploadFormHelper.methodname. */
    return {

        /* Initialize the page. */
        init: function(params){

            // Get the parameters.
            uploadPreviewUrl = params.uploadPreviewUrl;
            uploadStartUrl = params.uploadStartUrl;

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

            // Other form field related elements.
            $pointGenText = $('#auto_generate_points_page_section');

            // Button elements.
            $uploadStartButton = $('#id_upload_submit');
            $uploadAbortButton = $('#id_upload_abort_button');
            $startAnotherUploadForm = $('#id_start_another_upload_form');
            $proceedToManageMetadataForm = $('#id_proceed_to_manage_metadata_form');

            $uploadStartInfo = $('#upload_start_info');


            // Hide the after-upload buttons for now
            $startAnotherUploadForm.hide();
            $proceedToManageMetadataForm.hide();

            // Set onchange handlers for form fields.
            $(filesField).change( function(){
                updateFiles();
                updateFilesTable();
            });

            // Make sure the files table initially looks right
            updateFilesTable();


            // Upload button event handlers.
            $uploadStartButton.click(startAjaxImageUpload);
            $uploadAbortButton.click(abortAjaxUpload);
        }
    }
})();
