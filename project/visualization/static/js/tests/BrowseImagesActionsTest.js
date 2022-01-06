import fetchMock from '/static/js/fetch-mock.js';
const { test } = QUnit;
let browseActionHelper = null;
let originalWindowAlert = window.alert;
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

function assertUiStatus(assert, form, submissionShouldBeEnabled) {
    let submitButton = form.querySelector('button.submit');
    let actionSelectField = document.querySelector(
        'select[name=browse_action]');

    if (submissionShouldBeEnabled) {
        assert.equal(
            submitButton.disabled, false,
            "Submit button should be enabled");
        assert.equal(
            submitButton.textContent, "Go", "Submit button should say Go");
        assert.equal(
            actionSelectField.disabled, false,
            "Action select field should be enabled");
    }
    else {
        assert.equal(
            submitButton.disabled, true, "Submit button should be disabled");
        assert.equal(
            submitButton.textContent, "Working...",
            "Submit button should say Working");
        assert.equal(
            actionSelectField.disabled, true,
            "Action select field should be disabled");
    }
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
    if (newValue === 'annotate_all' || newValue === 'annotate_selected') {
        newValue = 'annotate';
    }
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

function mockSynchronousFormSubmit(form, submitStatus) {
    // Modify this form's submit handler such that 1) the core part of the
    // existing submit handler is still allowed to run, and 2) navigation to
    // the form's action URL ultimately doesn't happen.
    //
    // At the end of the submit handler, submit() is called on the form
    // element. That is the part that starts URL navigation. So, we overwrite
    // submit() here with a function that does not navigate anywhere, and sets
    // a flag confirming that the form was submitted.
    form.submit = () => {
        submitStatus.called = true;
    };
}


let formLookup = {
    annotate_all: {
        // Not sure how to pass in URLs from Django, so we'll just hardcode
        // here.
        actionPath: '/annotate_all/',
        hasFormFields: false,
    },
    annotate_selected: {
        actionPath: '/annotate_selected/',
        hasFormFields: false,
    },
    export_metadata: {
        formId: 'export-metadata-form',
        actionPath: '/source/1/export/metadata/',
        hasFormFields: false,
    },
    export_annotations: {
        formId: 'export-annotations-form',
        actionPath: '/source/1/export/annotations/',
        hasFormFields: true,
    },
    export_annotations_cpc: {
        formId: 'export-annotations-cpc-ajax-form',
        actionPath: '/source/1/export/annotations_cpc_create_ajax/',
        hasFormFields: false,
        syncFormId: 'export-annotations-cpc-form',
    },
    export_image_covers: {
        formId: 'export-image-covers-form',
        actionPath: '/source/1/export/image_covers/',
        hasFormFields: true,
    },
    export_calcify_rates: {
        formId: 'export-calcify-rates-form',
        actionPath: '/source/1/calcification/stats_export/',
        hasFormFields: true,
    },
    delete_images: {
        formId: 'delete-images-ajax-form',
        actionPath: '/source/1/browse/delete_ajax/',
        hasFormFields: false,
        promptString: 'delete',
        syncFormId: 'refresh-browse-form',
    },
    delete_annotations: {
        formId: 'delete-annotations-ajax-form',
        actionPath: '/source/1/annotation/batch_delete_ajax/',
        hasFormFields: false,
        promptString: 'delete',
        syncFormId: 'refresh-browse-form',
    },
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
                'export_metadata',
                'export_annotations',
                'export_annotations_cpc',
                'export_image_covers',
                'export_calcify_rates',
                'delete_images',
                'delete_annotations',
            ],
            (assert, actionValue) => {
        changeAction(actionValue);
        assert.deepEqual(
            getVisibleActionFormIds(), [formLookup[actionValue].formId],
            "Should show the appropriate action form for the selections");
    });
});


QUnit.module("Confirmation prompts", (hooks) => {
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
            "No input",
            [
                ['delete_images', 'all'],
                ['delete_images', 'selected'],
                ['delete_annotations', 'all'],
                ['delete_annotations', 'selected'],
            ],
            (assert, [actionValue, imageSelectType]) => {

        changeAction(actionValue);
        changeImageSelectType(imageSelectType);
        let asyncForm = getVisibleActionForm();

        assertUrlPathEqual(
            assert, asyncForm.action,
            formLookup[actionValue].actionPath);

        // Mock window.prompt() so that we don't actually have to interact
        // with a prompt dialog.
        window.prompt = () => {
            // Enter nothing for the prompt input.
            return "";
        };

        // Submit.
        let promise = browseActionHelper.actionSubmit(new Event('dummyevent'));

        assert.notOk(promise, "Submission shouldn't have gone through");
        assertUiStatus(assert, asyncForm, true);
    });

    test.each(
            "Wrong input",
            [
                ['delete_images', 'all'],
                ['delete_images', 'selected'],
                ['delete_annotations', 'all'],
                ['delete_annotations', 'selected'],
            ],
            (assert, [actionValue, imageSelectType]) => {

        changeAction(actionValue);
        changeImageSelectType(imageSelectType);
        let asyncForm = getVisibleActionForm();

        assertUrlPathEqual(
            assert, asyncForm.action,
            formLookup[actionValue].actionPath);

        // Mock window.prompt() so that we don't actually have to interact
        // with a prompt dialog.
        window.prompt = () => {
            // Use a wrong input: the correct input plus one character.
            return formLookup[actionValue].promptString + "x";
        };

        // Submit.
        let promise = browseActionHelper.actionSubmit(new Event('dummyevent'));

        assert.notOk(promise, "Submission shouldn't have gone through");
        assertUiStatus(assert, asyncForm, true);
    });

    // Correct input is covered in the form submission tests.
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
        // Restore alert() and prompt() to native implementations
        window.alert = originalWindowAlert;
        window.prompt = originalWindowPrompt;
    });

    test.each(
            "Synchronous actions",
            [
                ['annotate_all', 'all'],
                ['annotate_selected', 'selected'],
                ['export_metadata', 'all'],
                ['export_metadata', 'selected'],
                ['export_annotations', 'all'],
                ['export_annotations', 'selected'],
                ['export_image_covers', 'all'],
                ['export_image_covers', 'selected'],
                ['export_calcify_rates', 'all'],
                ['export_calcify_rates', 'selected'],
            ],
            (assert, [actionValue, imageSelectType]) => {

        changeAction(actionValue);
        changeImageSelectType(imageSelectType);
        let form = getVisibleActionForm();

        // Ensure that using the submit button doesn't actually navigate
        // to the URL.
        let submitStatus = {called: false};
        mockSynchronousFormSubmit(form, submitStatus);
        // Run the submit handler.
        // JS console gets a deprecation warning when dispatching an 'untrusted
        // submit event', so just call the submit handler directly.
        browseActionHelper.actionSubmit(new Event('dummyevent'));

        assert.ok(submitStatus.called, "Form should have submitted");

        assertUrlPathEqual(
            assert, form.action, formLookup[actionValue].actionPath);

        let hasFormFields = formLookup[actionValue].hasFormFields;
        let expectedFormData = hasFormFields ? {'field1': ""} : {};
        if (imageSelectType === 'selected') {
            expectedFormData['image_form_type'] = "ids";
            expectedFormData['ids'] = "1,2,3";
        }
        assertFormDataEqual(assert, form, expectedFormData);
    });

    test.each(
            "Async actions: request",
            [
                ['export_annotations_cpc', 'all'],
                ['export_annotations_cpc', 'selected'],
                ['delete_images', 'all'],
                ['delete_images', 'selected'],
                ['delete_annotations', 'all'],
                ['delete_annotations', 'selected'],
            ],
            (assert, [actionValue, imageSelectType]) => {

        changeAction(actionValue);
        changeImageSelectType(imageSelectType);
        let asyncForm = getVisibleActionForm();

        assertUrlPathEqual(
            assert, asyncForm.action,
            formLookup[actionValue].actionPath);

        if (formLookup[actionValue].promptString) {
            // Mock window.prompt() so that we don't actually have to interact
            // with a prompt dialog.
            window.prompt = () => {
                return formLookup[actionValue].promptString;
            };
        }
        // Mock window.fetch() so that the request isn't actually made.
        fetchMock.post(
            window.location.origin + formLookup[actionValue].actionPath,
            {'success': true});
        // Ensure that the subsequent synchronous form submission doesn't
        // actually navigate to the URL.
        let syncForm = document.getElementById(
            formLookup[actionValue].syncFormId);
        let submitStatus = {called: false};
        mockSynchronousFormSubmit(syncForm, submitStatus);

        // Submit.
        let promise = browseActionHelper.actionSubmit(new Event('dummyevent'));

        // Check UI status before response.
        assertUiStatus(assert, asyncForm, false);

        // Test what was submitted for the async request.
        let hasFormFields = formLookup[actionValue].hasFormFields;
        let expectedFormData = hasFormFields ? {'field1': ""} : {};
        if (imageSelectType === 'selected') {
            expectedFormData['image_form_type'] = "ids";
            expectedFormData['ids'] = "1,2,3";
        }
        assertFormDataEqual(assert, asyncForm, expectedFormData);

        // Wait for the response.
        const done = assert.async();
        promise.then((response) => {
            assert.ok(
                submitStatus.called,
                "Synchronous form should have submitted");

            // Tell QUnit that the test can finish.
            done();
        });
    });

    test.each(
            "Async actions: success response",
            [
                ['export_annotations_cpc', 'all'],
                ['export_annotations_cpc', 'selected'],
                ['delete_images', 'all'],
                ['delete_images', 'selected'],
                ['delete_annotations', 'all'],
                ['delete_annotations', 'selected'],
            ],
            (assert, [actionValue, imageSelectType]) => {

        changeAction(actionValue);
        changeImageSelectType(imageSelectType);
        let asyncForm = getVisibleActionForm();

        if (formLookup[actionValue].promptString) {
            // Mock window.prompt() so that we don't actually have to interact
            // with a prompt dialog.
            window.prompt = () => {
                return formLookup[actionValue].promptString;
            };
        }
        // Mock window.fetch() so that the request isn't actually made.
        fetchMock.post(
            window.location.origin + formLookup[actionValue].actionPath,
            {'success': true});
        // Ensure that the subsequent synchronous form submission doesn't
        // actually navigate to the URL.
        let syncForm = document.getElementById(
            formLookup[actionValue].syncFormId);
        let submitStatus = {called: false};
        mockSynchronousFormSubmit(syncForm, submitStatus);

        // Submit.
        let promise = browseActionHelper.actionSubmit(new Event('dummyevent'));

        // Wait for the response.
        const done = assert.async();
        promise.then((response) => {
            // Check UI status after the response comes back.
            assertUiStatus(assert, asyncForm, true);

            assert.ok(
                submitStatus.called,
                "Synchronous form should have submitted");

            // Test what was submitted for the sync request.
            assertFormDataEqual(assert, syncForm, {});

            // Tell QUnit that the test can finish.
            done();
        });
    });

    test.each(
            "Async actions: failure response",
            [
                ['export_annotations_cpc', 'all'],
                ['export_annotations_cpc', 'selected'],
                ['delete_images', 'all'],
                ['delete_images', 'selected'],
                ['delete_annotations', 'all'],
                ['delete_annotations', 'selected'],
            ],
            (assert, [actionValue, imageSelectType]) => {

        changeAction(actionValue);
        changeImageSelectType(imageSelectType);

        if (formLookup[actionValue].promptString) {
            // Mock window.prompt() so that we don't actually have to interact
            // with a prompt dialog.
            window.prompt = () => {
                return formLookup[actionValue].promptString;
            };
        }
        // Mock window.fetch() so that the request isn't actually made.
        // Response should indicate a server error.
        fetchMock.post(
            window.location.origin + formLookup[actionValue].actionPath,
            new Response(
                null, {status: 500, statusText: "Internal Server Error"}));

        // Mock window.alert() so that we don't actually have to interact
        // with an alert dialog. Also, so we can assert its contents.
        let alertMessage = null;
        window.alert = (message) => {
            alertMessage = message;
        };
        // Be able to check if the sync form submitted or not (it shouldn't).
        let syncForm = document.getElementById(
            formLookup[actionValue].syncFormId);
        let submitStatus = {called: false};
        mockSynchronousFormSubmit(syncForm, submitStatus);

        // Submit.
        let promise = browseActionHelper.actionSubmit(new Event('dummyevent'));

        // Wait for the response.
        const done = assert.async();
        promise.then((response) => {
            assert.notOk(
                submitStatus.called,
                "Synchronous form should not have submitted");

            assert.equal(
                alertMessage,
                "There was an error:" +
                "\nError: Internal Server Error" +
                "\nIf the problem persists, please notify us on the forum.",
                "Alert message should be as expected");

            // Tell QUnit that the test can finish.
            done();
        });
    });

    // TODO: Test actions with search-filtered images, not just all images and selected images. This would require loading the test page's Django template with different args.
});
