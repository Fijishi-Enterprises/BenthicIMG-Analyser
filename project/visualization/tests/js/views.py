from django.shortcuts import render

from lib.decorators import debug_required
from lib.forms import DummyForm
from lib.utils import paginate


@debug_required
def browse_images_actions(request):

    return render(request, 'lib/qunit_running.html', {
        # Context for the QUnit template

        'fixture_template': 'visualization/browse_images_actions.html',
        'javascript_functionality_modules': [
            'js/jquery.min.js', 'js/util.js', 'js/BrowseActionHelper.js'],
        'javascript_test_modules': ['js/tests/BrowseImagesActionsTest.js'],

        # Context for the template to test

        'source': dict(pk=1, confidence_threshold=80),
        'page_results': paginate(
            results=[1, 2, 3, 4], items_per_page=3, request_args=dict()),
        'links': dict(
            annotation_tool_first_result='/annotate_all/',
            annotation_tool_page_results=['/annotate_selected/']),
        'empty_message': "",
        # TODO: Have multiple possibilities for these args: no search (done here), filter search, image-ID search. Perhaps this test view can take GET args to decide test options like this.
        'image_search_form': DummyForm(),
        'hidden_image_form': None,

        'can_annotate': True,
        'can_export_cpc_annotations': True,
        'can_manage_source_data': True,

        'export_annotations_form': DummyForm(),
        'export_image_covers_form': DummyForm(),

        'export_calcify_rates_form': DummyForm(),
        'calcify_table_form': DummyForm(),
        'source_calcification_tables': [
            dict(name="Table name", pk=2, description="Table description")],
        'default_calcification_tables': [
            dict(name="Default table", pk=1, description="Table description")],

        'cpc_prefs_form': DummyForm(),
        'previous_cpcs_status': 'none',
    })
