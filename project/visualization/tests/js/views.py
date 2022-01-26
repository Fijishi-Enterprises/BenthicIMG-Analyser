from django.shortcuts import render
from django.template.loader import render_to_string

from lib.decorators import debug_required
from lib.forms import DummyForm
from lib.utils import paginate


@debug_required
def browse_images_actions(request):

    test_template_name = 'visualization/browse_images_actions.html'

    def create_test_template_context(**kwargs):
        """
        Create a dict which starts with default values, and updates values
        with any passed kwargs.
        """
        context = {
            'source': dict(pk=1, confidence_threshold=80),
            'page_results': paginate(
                results=[1, 2, 3, 4], items_per_page=3, request_args=dict()),
            'links': dict(
                annotation_tool_first_result='/annotate_all/',
                annotation_tool_page_results=['/annotate_selected/']),
            'empty_message': "",

            'hidden_image_form': None,

            'can_annotate': True,
            'can_export_cpc_annotations': True,
            'can_manage_source_data': True,

            'export_annotations_form': DummyForm(),
            'export_image_covers_form': DummyForm(),

            'export_calcify_rates_form': DummyForm(),
            'calcify_table_form': DummyForm(),
            'source_calcification_tables': [dict(
                name="Table name", pk=2, description="Table description")],
            'default_calcification_tables': [dict(
                name="Default table", pk=1, description="Table description")],

            # For this particular form, the template only includes
            # specific fields. We'll pick a text field, since that's more
            # straightforward to include than a radio button field.
            'cpc_prefs_form': DummyForm(local_code_filepath='C:/codes.txt'),
            'previous_cpcs_status': 'none',
        }
        context.update(**kwargs)
        return context

    test_template_contexts = {
        'all_images': create_test_template_context(),
        'with_search_filters': create_test_template_context(**{
            'hidden_image_form': DummyForm(
                aux1='Site A',
                photo_date_0='date_range', photo_date_1='', photo_date_2='',
                photo_date_3='2021-01-01', photo_date_4='2021-06-30',
            ),
        }),
    }

    fixtures = {
        fixture_name: render_to_string(test_template_name, context, request)
        for fixture_name, context in test_template_contexts.items()}

    return render(request, 'lib/qunit_running.html', {
        'fixtures': fixtures,
        'javascript_functionality_modules': [
            'js/jquery.min.js', 'js/util.js', 'js/BrowseActionHelper.js'],
        'javascript_test_modules': ['js/tests/BrowseImagesActionsTest.js'],
    })
