import fetchMock from '/static/js/fetch-mock.js';
const { test } = QUnit;
let browseActionHelper = null;
let originalWindowPrompt = window.prompt;


function assertFormDataEqual(assert, actualForm, expectedFormData) {
    let formData = new FormData(actualForm);
    let formDataContents = Object.fromEntries(formData.entries());

    // We won't try to match the CSRF token value since it's random.
    assert.true(
        'csrfmiddlewaretoken' in formDataContents,
        "CSRF token should be present in form");
    delete formDataContents['csrfmiddlewaretoken'];

    assert.deepEqual(
        formDataContents, expectedFormData, "Form data should be as expected");
}

/* Check that the part of actualUrl after the domain name (but including the
slash) matches expectedUrlPath. */
function assertUrlPathEqual(assert, actualUrl, expectedUrlPath) {
    // window.location.origin gets the scheme, domain, and port, like:
    // "http://localhost:8000"
    assert.equal(
        actualUrl, window.location.origin + expectedUrlPath,
        "URL path should be as expected");
}

function changeAction(newValue) {
    let actionSelectField = document.querySelector(
        'select[name=browse_action]');
    actionSelectField.value = newValue;
    actionSelectField.dispatchEvent(new Event('change'));
}

function changeImageSelectType(newValue) {
    let imageSelectTypeField = document.querySelector(
        'select[name=image_select_type]');
    imageSelectTypeField.value = newValue;
    imageSelectTypeField.dispatchEvent(new Event('change'));
}

/* Return the IDs of all visible action forms. */
function getVisibleActionFormIds() {
  let actionBox = document.getElementById('action-box');
  let actionForms = actionBox.querySelectorAll('form');
  let visibleActionFormIds = [];
  actionForms.forEach((form) => {
    if (!form.hidden) {
      visibleActionFormIds.push(form.id);
    }
  });
  return visibleActionFormIds;
}

/* Assume there is one visible action form, and return that form. */
function getVisibleActionForm() {
    let actionBox = document.getElementById('action-box');
    let actionForms = actionBox.querySelectorAll('form');
    let visibleForm = null;
    actionForms.forEach((form) => {
        if (!form.hidden) {
            visibleForm = form;
        }
    });
    return visibleForm;
}

function mockSynchronousFormSubmit(form) {
    // Modify this form's submit handler such that 1) the core part of the
    // existing submit handler is still allowed to run, and 2) navigation to
    // the form's action URL ultimately doesn't happen.
    //
    // At the end of the submit handler, submit() is called on the form
    // element. That is the part that starts URL navigation. So, we overwrite
    // submit() here with a no-op.
    form.submit = () => {};
}


// QUnit module syntax: https://api.qunitjs.com/QUnit/module/

QUnit.module("Constructor", (hooks) => {
    test("Main constructor should succeed", function(assert) {
        browseActionHelper = new BrowseActionHelper([1, 2, 3]);
        assert.ok(browseActionHelper, "Constructor should get initialized");
    });
});


/* Test that when each particular action is selected, the appropriate
action form is shown. */
QUnit.module("Form visibility", (hooks) => {
    hooks.beforeEach(() => {
        browseActionHelper = new BrowseActionHelper([1, 2, 3]);
    });

    test("No action", (assert) => {
        changeAction('annotate');
        changeAction('');
        assert.deepEqual(
            getVisibleActionFormIds(), [],
            "Should have no visible action form when no action is chosen");
    });

    test("Annotate all", (assert) => {
        changeAction('annotate');
        changeImageSelectType('all');
        assert.deepEqual(
            getVisibleActionFormIds(), ['annotate-all-form'],
            "Should show the appropriate action form for the selections");
    });

    test("Annotate selected", (assert) => {
        changeAction('annotate');
        changeImageSelectType('selected');
        assert.deepEqual(
            getVisibleActionFormIds(), ['annotate-selected-form'],
            "Should show the appropriate action form for the selections");
    });

    // https://api.qunitjs.com/QUnit/test.each/
    test.each(
            "Export and management actions",
            [
                ['export_metadata', 'export-metadata-form'],
                ['export_annotations', 'export-annotations-form'],
                ['export_annotations_cpc', 'export-annotations-cpc-ajax-form'],
                ['export_image_covers', 'export-image-covers-form'],
                ['export_calcify_rates', 'export-calcify-rates-form'],
                ['delete_images', 'delete-images-ajax-form'],
                ['delete_annotations', 'delete-annotations-ajax-form'],
            ],
            (assert, [actionValue, actionFormId]) => {
        changeAction(actionValue);
        assert.deepEqual(
            getVisibleActionFormIds(), [actionFormId],
            "Should show the appropriate action form for the selections");
    });
});


/* Test submission of each form, asserting what params were submitted and
 to what URL, and how responses are handled. */
QUnit.module("Form submission", (hooks) => {
    hooks.beforeEach(() => {
        browseActionHelper = new BrowseActionHelper([1, 2, 3]);
    });
    hooks.afterEach(() => {
        // Restore fetch() to its native implementation
        fetchMock.reset();
        // Restore prompt() to its native implementation
        window.prompt = originalWindowPrompt;
    });

    test.each(
            "Synchronous actions with all images",
            [
                ['annotate', '/annotate_all/', false],
                // Not sure how to pass in URLs from Django, so we'll just
                // hardcode here.
                ['export_metadata', '/source/1/export/metadata/', false],
                ['export_annotations',
                 '/source/1/export/annotations/', true],
                ['export_image_covers',
                 '/source/1/export/image_covers/', true],
                ['export_calcify_rates',
                 '/source/1/calcification/stats_export/', true],
            ],
            (assert, [actionValue, actionPath, hasFormFields]) => {

        changeAction(actionValue);
        changeImageSelectType('all');
        let form = getVisibleActionForm();

        // Ensure that using the submit button doesn't actually navigate
        // to the URL.
        mockSynchronousFormSubmit(form);
        // Run the submit handler.
        // JS console gets a deprecation warning when dispatching an 'untrusted
        // submit event', so just call the submit handler directly.
        browseActionHelper.actionSubmit(new Event('dummyevent'));

        assertUrlPathEqual(assert, form.action, actionPath);

        let expectedFormData = hasFormFields ? {'field1': ""} : {};
        assertFormDataEqual(assert, form, expectedFormData);
    });

    test.each(
            "Synchronous actions with current page's images",
            [
                ['annotate', '/annotate_selected/', false],
                ['export_metadata', '/source/1/export/metadata/', false],
                ['export_annotations',
                 '/source/1/export/annotations/', true],
                ['export_image_covers',
                 '/source/1/export/image_covers/', true],
                ['export_calcify_rates',
                 '/source/1/calcification/stats_export/', true],
            ],
            (assert, [actionValue, actionPath, hasFormFields]) => {

        changeAction(actionValue);
        changeImageSelectType('selected');
        let form = getVisibleActionForm();

        mockSynchronousFormSubmit(form);
        browseActionHelper.actionSubmit(new Event('dummyevent'));

        assertUrlPathEqual(assert, form.action, actionPath);

        let expectedFormData = hasFormFields ? {'field1': ""} : {};
        expectedFormData['image_form_type'] = "ids";
        expectedFormData['ids'] = "1,2,3";
        assertFormDataEqual(assert, form, expectedFormData);
    });

    // TODO: Synchronous actions with filtered images. This requires loading the Django template with different args.

    // TODO: Consider splitting the below into multiple tests: request testing and response testing.

    test.each(
            "Async action success with all images",
            [
                ['export_annotations_cpc',
                 '/source/1/export/annotations_cpc_create_ajax/', false,
                 null, 'export-annotations-cpc-form'],
                ['delete_images', '/source/1/browse/delete_ajax/', false,
                 'delete', 'refresh-browse-form'],
                ['delete_annotations',
                 '/source/1/annotation/batch_delete_ajax/', false,
                 'delete', 'refresh-browse-form'],
            ],
            (assert,
             [actionValue, actionPath, hasFormFields,
              promptString, syncFormId]) => {

        changeAction(actionValue);
        changeImageSelectType('all');
        let asyncForm = getVisibleActionForm();

        assertUrlPathEqual(assert, asyncForm.action, actionPath);

        if (promptString) {
            // Mock window.prompt() so that we don't actually have to interact
            // with a prompt dialog.
            window.prompt = () => {return promptString;};
        }
        // Mock window.fetch() so that the request isn't actually made.
        fetchMock.post(
            window.location.origin + actionPath,
            {'success': true});
        // Ensure that the subsequent synchronous form submission doesn't
        // actually navigate to the URL.
        let syncForm = document.getElementById(syncFormId);
        mockSynchronousFormSubmit(syncForm);

        // Submit.
        let promise = browseActionHelper.actionSubmit(new Event('dummyevent'));

        // Check UI status before response.
        let submitButton = asyncForm.querySelector('button.submit');
        assert.equal(
            submitButton.disabled, true, "Submit button should be disabled");
        assert.equal(
            submitButton.textContent, "Working...",
            "Submit button should say Working");
        let actionSelectField = document.querySelector(
            'select[name=browse_action]');
        assert.equal(
            actionSelectField.disabled, true,
            "Action select field should be disabled");

        // Test what was submitted for the async request.
        let expectedFormData = hasFormFields ? {'field1': ""} : {};
        assertFormDataEqual(assert, asyncForm, expectedFormData);

        // Test what was submitted for the sync request.
        assertFormDataEqual(assert, syncForm, {});

        // Check UI status after response.
        const done = assert.async();
        promise.then((response) => {
            assert.equal(
                submitButton.disabled, false,
                "Submit button should be enabled");
            assert.equal(
                submitButton.textContent, "Go", "Submit button should say Go");
            assert.equal(
                actionSelectField.disabled, false,
                "Action select field should be enabled");
            done();
        });
    });
});
