// Selects all of the checkboxes given the value of the check all box.
function selectall() {
    var id = "#id_selected";
    if ($(id).attr('checked'))
        setCheckedRows(true);
    else
        setCheckedRows(false);
}

// Given the row/column, this will return the value at that cell in the table.
function getCellValue(row, column)
{
    return $('#metadataFormTable')[0].rows[row+1].cells[column+1].childNodes[0].value;
}

// Given the row/column, this sets the value in that cell to what value is.
function setCellValue(row, column, value)
{
    var field = $('#metadataFormTable')[0].rows[row+1].cells[column+1].childNodes[0];

    // Check if the old and new values are different; if so, mark the cell
    // as changed.
    if (field.value !== value) {
        updateMetadataChangeStatus($(field));
    }
    // Set the new value.
    field.value = value;
}

// This returns an bool array that represents what checkboxes are checked.
function checkedRows() {
    var rows = $("#metadataFormTable tr").length;
    var checkedRows = new Array();
    for (var i = 0; i < rows; i++)
    {
        var id = "#id_form-" + i + "-selected";
        if ($(id).attr('checked') != null)
            checkedRows[i] = true;
        else
            checkedRows[i] = false;
    }
    return checkedRows;
}

// Takes a boolean value that sets all of the checkboxes to that value.
function setCheckedRows(checked) {
    var rows = $("#metadataFormTable tr").length;
    for (var i = 0; i < rows; i++)
    {
        var id = "#id_form-" + i + "-selected";
        $(id).attr("checked", checked);
    }
}

// This will handle updating all checked rows in the form.
// This is called whenever a user types in one of the text fields.
// row and column correspond to the text field that was just typed in.
function updateCheckedRowFields(row, column) {
    var checked = checkedRows();

    // If the edited text field wasn't checked, then do nothing.
    if (checked[row] == false) {return;}

    var input = getCellValue(row, column);
    for (var i = 0; i < checked.length; i++) {
        if(checked[i] == true) {setCellValue(i, column, input);}
    }
}

// Update indicators that a value in the form has changed.
function updateMetadataChangeStatus($field) {

    // Un-disable the Save Edits button
    $('#id_metadata_form_save_button').prop('disabled', false);

    // Update text next to the Save button
    $('#id_metadata_save_status').text("There are unsaved changes");

    // Add warning when trying to navigate away
    util.pageLeaveWarningEnable("You have unsaved changes.");

    // Style the changed field differently, so the user can keep track of
    // what's changed
    $field.addClass('changed').removeClass('error');
}

// This initializes the form with the correct bindings.
function setUpBindings(params) {
    // Get all form input fields except type="hidden"
    var $editableFields = $('#metadataFormTable').find(
        'input[type="text"],input[type="number"],textarea');

    $editableFields.each(function() {
        if (this.id.endsWith('photo_date')) {
            $(this).datepicker({ dateFormat: 'yy-mm-dd' });
            setRowColumnBindingsChangeDate($(this));
        }
        else {
            setRowColumnBindingsChange($(this));
            setRowColumnBindingsKeyUp($(this));
        }
    });

    // When the top checkbox is checked/unchecked, check/uncheck
    // all the checkboxes
    $('#id_selected').bind("change", function() {
        selectall();
    });

    // When the metadata save button is clicked...
    $('#id_metadata_form_save_button').bind(
        "click", submitMetadataForm.curry(params.metadataSaveAjaxUrl));
}

// This will set a key-up binding that calls
// updateCheckedRowFields with the given row and column of the table form.
function setRowColumnBindingsKeyUp($element) {
    $element.bind("keyup", function() {
        var row_index = $(this).parent().parent().index('tr');
        var col_index = $(this).parent().index('tr:eq('+row_index+') td');
        updateCheckedRowFields(row_index-1, col_index-1);
    });
}

function setRowColumnBindingsChange($field) {
    $field.bind("change", function() {
        // Update indicators that a value in the form
        // has changed.
        updateMetadataChangeStatus($(this));
    });
}

function setRowColumnBindingsChangeDate($field) {
    $field.bind("change", function() {
        // Update indicators that a value in the form
        // has changed.
        updateMetadataChangeStatus($(this));

        // Update checked rows.
        var row_index = $(this).parent().parent().index('tr');
        var col_index = $(this).parent().index('tr:eq('+row_index+') td');
        updateCheckedRowFields(row_index-1, col_index-1);
    });
}

// Submit the metadata form (using Ajax).
function submitMetadataForm(metadataSaveAjaxUrl) {
    // Disable the save button
    $('#id_metadata_form_save_button').prop('disabled', true);

    // Remove any error messages from a previous edit attempt
    $('ul#id_metadata_errors_list').empty();

    // Update text next to the Save button
    $('#id_metadata_save_status').text("Now saving...");

    // Submit the metadata form with Ajax
    $.ajax({
        // URL to make request to
        url: metadataSaveAjaxUrl,
        // Data to send in the request
        data: $('#id_metadata_form').serialize(),
        type: 'POST',
        // Callbacks
        success: metadataSaveAjaxResponseHandler,
        error: util.handleServerError
    });
}

// This function runs when the metadata-save-via-Ajax returns from
// the server side.
function metadataSaveAjaxResponseHandler(response) {
    // Update text next to the Save button
    if (response.status === 'success') {
        $('#id_metadata_save_status').text("All changes saved");

        // Disable "You have unsaved changes" warning
        // when trying to navigate away
        util.pageLeaveWarningDisable();

        // Remove field stylings
        var $editableFields = $('#metadataFormTable').find(
            'input[type="text"],input[type="number"],textarea');
        $editableFields.removeClass('changed error');
    }
    else {  // 'error'
        $('#id_metadata_save_status').text(
            "There were error(s); couldn't save");

        var $errorsList = $('ul#id_metadata_errors_list');
        var numOfErrors = response.errors.length;

        for (var i = 0; i < numOfErrors; i++) {
            // Display the error message(s) next to the Save button
            $errorsList.append($('<li>').text(
                response.errors[i].errorMessage
            ));
            // Style the field to indicate an error
            $('#' + response.errors[i].fieldId)
                .addClass('error').removeClass('changed');
        }
    }
}

function initMetadataForm(params) {
    // Initialize save status
    $('#id_metadata_save_status').text("All changes saved");
    $('#id_metadata_form_save_button').prop('disabled', true);

    // Set up event bindings
    setUpBindings(params);
}