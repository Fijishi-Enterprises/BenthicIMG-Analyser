let browseActionHelper = new BrowseActionHelper([1, 2, 3]);

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


QUnit.module('constructor', function() {
    QUnit.test('main constructor should succeed', function(assert) {
        assert.ok(browseActionHelper);
    });
});

QUnit.module('form visibility', function() {
    QUnit.test('no action', function(assert) {
        changeAction('annotate');
        changeAction('');
        assert.deepEqual(getVisibleActionFormIds(), []);
    });

    QUnit.test('annotate all', function(assert) {
        changeAction('annotate');
        changeImageSelectType('all');
        assert.deepEqual(
            getVisibleActionFormIds(), ['annotate-all-form']);
    });

    QUnit.test('annotate selected', function(assert) {
        changeAction('annotate');
        changeImageSelectType('selected');
        assert.deepEqual(
            getVisibleActionFormIds(), ['annotate-selected-form']);
    });

    QUnit.test('export metadata', function(assert) {
        changeAction('export_metadata');
        assert.deepEqual(
            getVisibleActionFormIds(), ['export-metadata-form']);
    });

    QUnit.test('export annotations csv', function(assert) {
        changeAction('export_annotations');
        assert.deepEqual(
            getVisibleActionFormIds(), ['export-annotations-form']);
    });

    QUnit.test('export annotations cpc', function(assert) {
        changeAction('export_annotations_cpc');
        assert.deepEqual(
            getVisibleActionFormIds(), ['export-annotations-cpc-ajax-form']);
    });

    QUnit.test('export image covers', function(assert) {
        changeAction('export_image_covers');
        assert.deepEqual(
            getVisibleActionFormIds(), ['export-image-covers-form']);
    });

    QUnit.test('export calcify rates', function(assert) {
        changeAction('export_calcify_rates');
        assert.deepEqual(
            getVisibleActionFormIds(), ['export-calcify-rates-form']);
    });

    QUnit.test('delete images', function(assert) {
        changeAction('delete_images');
        assert.deepEqual(
            getVisibleActionFormIds(), ['delete-images-ajax-form']);
    });

    QUnit.test('delete annotations', function(assert) {
        changeAction('delete_annotations');
        assert.deepEqual(
            getVisibleActionFormIds(), ['delete-annotations-ajax-form']);
    });
});

// TODO: Test submission of each form; hopefully we can assert what was submitted and to what URL.
