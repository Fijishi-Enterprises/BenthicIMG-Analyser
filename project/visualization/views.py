from django.conf import settings
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.db import transaction
from django.forms import modelformset_factory
from django.forms.formsets import formset_factory
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from .forms import CheckboxForm, StatisticsSearchForm, ImageSearchForm, \
    PatchSearchOptionsForm, HiddenForm, create_image_filter_form
from accounts.utils import get_robot_user
from annotations.models import Annotation
from images.forms import MetadataFormForGrid, BaseMetadataFormSet
from images.models import Source, Image, Metadata, Point
from images.utils import delete_images
from labels.models import LabelGroup, Label
from lib.decorators import source_visibility_required, source_permission_required
from lib.utils import paginate


@source_visibility_required('source_id')
def browse_images(request, source_id):
    """
    Grid of a source's images.
    """
    source = get_object_or_404(Source, id=source_id)

    # Defaults
    empty_message = "No image results."
    image_search_form = ImageSearchForm(
        source=source, has_annotation_status=True)
    hidden_image_form = None

    # The primary way to filter images is by POST params due to the possible
    # length of some of the params. However, in some cases like the source main
    # page's image-status links, it can be easier to use GET.
    image_form = create_image_filter_form(
        request.POST or request.GET, source, has_annotation_status=True)
    if image_form:
        if image_form.is_valid():
            image_results = image_form.get_images()
            hidden_image_form = HiddenForm(forms=[image_form])
        else:
            image_results = Image.objects.none()
            empty_message = "Search parameters were invalid."

        # If a search form was submitted, use that as the displayed
        # search form. Otherwise we'll display a default-values search form.
        if isinstance(image_form, ImageSearchForm):
            image_search_form = image_form
    else:
        # Coming from a straight link or URL entry
        image_results = Image.objects.filter(source=source)

    image_results = image_results.order_by('metadata__name')

    page_results = paginate(
        image_results,
        settings.BROWSE_DEFAULT_THUMBNAILS_PER_PAGE,
        request.POST)

    if page_results.paginator.count > 0:
        page_image_ids = [
            int(pk)
            for pk in page_results.object_list.values_list('pk', flat=True)]
        links = dict(
            annotation_tool_first_result=
                reverse('annotation_tool', args=[image_results[0].pk]),
            annotation_tool_page_results=
                [reverse('annotation_tool', args=[pk])
                 for pk in page_image_ids],
            browse=reverse('browse_images', args=[source.pk]),
            delete=reverse('browse_delete_ajax', args=[source.pk]),
            export_metadata=reverse('export_metadata', args=[source.pk]),
            export_annotations_simple=reverse(
                'export_annotations_simple', args=[source.pk]),
            export_annotations_full=reverse(
                'export_annotations_full', args=[source.pk]),
            export_image_covers=reverse(
                'export_image_covers', args=[source.pk]),
        )
    else:
        page_image_ids = None
        links = None

    return render(request, 'visualization/browse_images.html', {
        'source': source,
        'image_search_form': image_search_form,
        'page_results': page_results,
        'page_image_ids': page_image_ids,
        'links': links,
        'hidden_image_form': hidden_image_form,
        'empty_message': empty_message,
    })


@source_permission_required('source_id', perm=Source.PermTypes.EDIT.code)
def edit_metadata(request, source_id):
    """
    Grid of editable metadata fields.
    """
    source = get_object_or_404(Source, id=source_id)

    # Defaults
    empty_message = "No image results."
    image_search_form = ImageSearchForm(
        source=source, has_annotation_status=True)

    image_form = create_image_filter_form(
        request.POST or request.GET, source, has_annotation_status=True)
    if image_form:
        if image_form.is_valid():
            image_results = image_form.get_images()
        else:
            image_results = Image.objects.none()
            empty_message = "Search parameters were invalid."

        # If a search form was submitted, use that as the displayed
        # search form. Otherwise we'll display a default-values search form.
        if isinstance(image_form, ImageSearchForm):
            image_search_form = image_form
    else:
        # Coming from a straight link or URL entry
        image_results = Image.objects.filter(source=source)

    image_results = image_results.order_by('metadata__name')
    num_images = image_results.count()

    # Formset of MetadataForms.
    MetadataFormSet = modelformset_factory(
        Metadata, form=MetadataFormForGrid, formset=BaseMetadataFormSet)
    # Separate formset that controls the checkboxes.
    CheckboxFormSet = formset_factory(CheckboxForm)

    # Initialize the form set with the existing metadata values.
    # Ensure that each form gets the source.
    metadata_objs = \
        Metadata.objects.filter(image__in=image_results).order_by('name')
    metadata_formset = MetadataFormSet(
        queryset=metadata_objs,
        form_kwargs={'source': source})

    # Initialize the checkbox parts.
    initValues = {
        'form-TOTAL_FORMS': '%s' % num_images,
        'form-INITIAL_FORMS': '%s' % num_images,
    }
    checkbox_formset = CheckboxFormSet(initValues)

    statuses = [img.get_annotation_status_str() for img in image_results]
    # Put all the formset table stuff together in an iterable
    metadata_rows = zip(
        metadata_formset.forms,
        checkbox_formset.forms,
        image_results,
        statuses,
    )

    select_all_form = CheckboxForm()

    return render(request, 'visualization/edit_metadata.html', {
        'source': source,
        'num_images': num_images,
        'image_search_form': image_search_form,
        'metadata_formset': metadata_formset,
        'select_all_form': select_all_form,
        'metadata_rows': metadata_rows,
        'empty_message': empty_message,
    })


@source_visibility_required('source_id')
def browse_patches(request, source_id):
    """
    Grid of a source's point patches.
    """
    source = get_object_or_404(Source, id=source_id)

    # Defaults
    empty_message = (
        "Use the form to retrieve image patches"
        " corresponding to annotated points."
    )
    annotation_results = Annotation.objects.none()
    image_search_form = ImageSearchForm(
        source=source, has_annotation_status=False)
    patch_search_form = PatchSearchOptionsForm(source=source)
    hidden_image_and_patch_form = None

    image_form = create_image_filter_form(
        request.POST or request.GET, source, has_annotation_status=False)
    if request.POST:
        patch_search_form = PatchSearchOptionsForm(request.POST, source=source)

    if image_form:
        if image_form.is_valid() and patch_search_form.is_valid():
            image_results = image_form.get_images()
            annotation_results = patch_search_form.get_annotations(
                image_results)
            hidden_image_and_patch_form = \
                HiddenForm(forms=[image_form, patch_search_form])
            empty_message = "No patch results."
        else:
            empty_message = "Search parameters were invalid."

        # If a search form was submitted, use that as the displayed
        # search form. Otherwise we'll display a default-values search form.
        if isinstance(image_form, ImageSearchForm):
            image_search_form = image_form

    # Random order
    annotation_results = annotation_results.order_by('?')

    page_results = paginate(
        annotation_results,
        settings.BROWSE_DEFAULT_THUMBNAILS_PER_PAGE,
        request.POST)

    return render(request, 'visualization/browse_patches.html', {
        'source': source,
        'image_search_form': image_search_form,
        'patch_search_form': patch_search_form,
        'page_results': page_results,
        'hidden_image_and_patch_form': hidden_image_and_patch_form,
        'empty_message': empty_message,
    })


@source_permission_required(
    'source_id', perm=Source.PermTypes.EDIT.code, ajax=True)
def edit_metadata_ajax(request, source_id):
    """
    Submitting the metadata-edit form (an Ajax form).
    """
    source = get_object_or_404(Source, id=source_id)
    MetadataFormSet = modelformset_factory(
        Metadata, form=MetadataFormForGrid, formset=BaseMetadataFormSet)
    formset = MetadataFormSet(
        request.POST, form_kwargs={'source': source})

    if formset.is_valid():
        # Save the edits
        formset.save()
        return JsonResponse(dict(
            status='success',
        ))
    else:
        # Don't save; display the errors on the page
        error_list = []

        for form in formset:

            # TODO: Would be nice to list the errors in the order they
            # appear in the form
            for field_name, error_messages in form.errors.iteritems():

                # The form prefix looks something like form-2. The id of the
                # form field element is expected to look like id_form-2-date.
                field_id = 'id_' + form.prefix + '-' + field_name

                # Get the human-readable name for this field.
                field_label = form[field_name].label

                # Get the image this field corresponds to, then get the
                # name (usually is the filename) of that image.
                metadata = form.instance
                image_name = metadata.name
                if image_name == '':
                    image_name = "(Unnamed image)"

                for raw_error_message in error_messages:

                    error_message = '{image_name} | {field_label} | {raw_error_message}'.format(
                        image_name=image_name,
                        field_label=field_label,
                        raw_error_message=raw_error_message,
                    )

                    error_list.append(dict(
                        fieldId=field_id,
                        errorMessage=error_message,
                    ))

        # There were form errors. Return the errors so they can be
        # added to the on-page form via Javascript.
        return JsonResponse(dict(
            status='error',
            errors=error_list,
        ))


@require_POST
@source_permission_required(
    'source_id', perm=Source.PermTypes.EDIT.code, ajax=True)
def browse_delete_ajax(request, source_id):
    """
    From the browse images page, select delete from the action form.
    """
    source = get_object_or_404(Source, id=source_id)

    image_form = create_image_filter_form(
        request.POST, source, has_annotation_status=True)
    if not image_form:
        # There's nothing invalid about a user wanting to delete all images
        # in the source, but it's somewhat plausible that we'd accidentally
        # reach this case if we screwed something up.
        #
        # It's not good to accidentally delete everything, and it's uncommon
        # to do it intentionally. So we'll play it safe.
        # If the user really wants to delete everything, they can simply
        # click Search with all fields at the defaults ("All" etc.)
        # and then choose Delete.
        return JsonResponse(dict(
            error=(
                "You must first use the search form"
                " or select images on the page to use the delete function."
            )
        ))
    if not image_form.is_valid():
        return JsonResponse(dict(
            error=(
                "There was an error with the form."
                " Nothing was deleted."
            )
        ))

    image_set = image_form.get_images()
    delete_count = delete_images(image_set)

    # This should appear on the next browse load.
    messages.success(
        request, 'The {num} selected images have been deleted.'.format(
            num=delete_count))

    return JsonResponse(dict(success=True))


@source_visibility_required('source_id')
# This is a potentially slow view that doesn't modify the database,
# so don't open a transaction for the view.
@transaction.non_atomic_requests
def generate_statistics(request, source_id):
    errors = []
    years = []
    label_table = []
    group_table = []
    #graph = []

    #generate form to select images to compute statistics for
    source = get_object_or_404(Source, id=source_id)

    #get image search filters
    if request.GET:

        #form to select descriptors to sort images
        form = StatisticsSearchForm(source_id, request.GET)

        if form.is_valid():
            labels = form.cleaned_data['labels']
            groups = form.cleaned_data['groups']

            # TODO: Fix
            imageArgs = image_search_args_to_queryset_args(form.cleaned_data, source)

            #Check that the specified set of images and/or labels was found
            if not labels and not groups:
                errors.append("Sorry you didn't specify any labels or groups!")

            #if no errors found, get data needed to plot line graph with
            # coverage on the y axis, and year on the x axis
            if not errors:

                images = Image.objects.filter(source=source, **imageArgs).distinct().select_related()
                patchArgs = dict([('image__'+k, imageArgs[k]) for k in imageArgs])

                #get all annotations for the source that contain the label
                if request.GET and request.GET.get('include_robot', ''):
                    all_annotations = Annotation.objects.filter(source=source, **patchArgs)
                else:
                    all_annotations = Annotation.objects.filter(source=source, **patchArgs).exclude(user=get_robot_user())


                #check that we found annotations
                if all_annotations:
                    #holds the data that gets passed to the graphing code
                    data = []

                    #Format computed data for the graph API to use
                    #TODO: pick easily distinguishable colours from
                    # http://search.cpan.org/~rokr/Color-Library-0.021/lib/Color/Library/Dictionary/WWW.pm
                    # and add them to bucket to be picked randomly
                    bucket = ['00FFFF','32CD32','A52A2A','DC143C','9370DB']
                    legends = []

                    #gets the years we have data for from the specified set of images
                    for image in images:
                        date = image.metadata.photo_date
                        if not date is None:
                            if not years.count(date.year):
                               years.append(date.year)
                    years.sort()

                    for label in labels:
                        table_yearly_counts = []
                        graph_yearly_counts = []
                        #get yearly counts that become y values for the label's line
                        for year in years:
                            #get the most recent for each point for every label specified
                            total_year_annotations =  all_annotations.filter(image__metadata__photo_date__year=year)
                            total_year_annotations_count = total_year_annotations.count()
                            label_year_annotations_count = total_year_annotations.filter(label=label).count()

                            #add up # of annotations, divide by total annotations, and times 100 to get % coverage
                            # done the way it is b/c we need to cast either num or denom as float to get float result,
                            # convert to %, round, then truncate by casting to int
                            try:
                                percent_coverage = (float(label_year_annotations_count)/total_year_annotations_count)*100
                            except ZeroDivisionError:
                                percent_coverage = 0
                            table_yearly_counts.append(round(percent_coverage,2))
                            table_yearly_counts.append(label_year_annotations_count)
                            graph_yearly_counts.append(int(percent_coverage))

                        data.append(graph_yearly_counts)

                        #add label name to legends
                        name = Label.objects.get(id=int(label)).name
                        legends.append(str(name))

                        #create table row to display
                        table_row = [name]
                        table_row.extend(table_yearly_counts)
                        label_table.append(table_row)
                        
                    for group in groups:
                        table_yearly_counts = []
                        graph_yearly_counts = []
                        #get yearly counts that become y values for the label's line
                        for year in years:
                            #get the most recent for each point for every label specified
                            total_year_annotations =  all_annotations.filter(image__metadata__photo_date__year=year)
                            total_year_annotations_count = total_year_annotations.count()
                            label_year_annotations_count = total_year_annotations.filter(label__group=group).count()

                            #add up # of annotations, divide by total annotations, and times 100 to get % coverage
                            # done the way it is b/c we need to cast either num or denom as float to get float result,
                            # convert to %, round, then truncate by casting to int
                            try:
                                percent_coverage = (float(label_year_annotations_count)/total_year_annotations_count)*100
                            except ZeroDivisionError:
                                percent_coverage = 0
                            table_yearly_counts.append(round(percent_coverage,2))
                            table_yearly_counts.append(label_year_annotations_count)
                            graph_yearly_counts.append(int(percent_coverage))

                        data.append(graph_yearly_counts)

                        #add label name to legends
                        name = LabelGroup.objects.get(id=int(group)).name
                        legends.append(str(name))

                        #create table row to display
                        table_row = [name]
                        table_row.extend(table_yearly_counts)
                        group_table.append(table_row)
                    """
                    #Create string of colors
                    colors_string = str(bucket[0: (len(labels)+len(groups))]).replace(' ', '').replace('[','').replace(']','').replace('\'', '')

                    #Create string of labels to put on legend
                    legends_string = str(legends).replace('[', '').replace(']','').replace(' ','').replace('\'', '').replace(',', '|')

                    #Get max y value and add 5 to it
                    max_y = max(map(max,data)) + 5

                    #Calculate new data proportional to max_y to scale graph
                    for elem in data:
                        elem[:] = [x*(100/max_y) for x in elem]

                    #Actually generate the graph now
                    graph = GChart('lc', data, encoding='text', chxt='x,y', chco=colors_string, chdl=legends_string)
                    #draw x axis values from lowest to highest year stepping by 1 year
                    graph.axes.range(0,min(years),max(years),1)
                    #draw y axis values from 0 to (max percent coverage + 5) stepping by 5
                    graph.axes.range(1,0,max_y,5)
                    #Define pixel size to draw graph
                    graph.size(400,400)
                    #Adds the title to the graph
                    graph.title('% Coverage over Years')
                    #Set the line thickness for each dataset
                    count = len(data)
                    while count > 0:
                        graph.line(3,0,0)
                        count -= 1
                    """
                else:
                    errors.append("No data found!")

        else:
            errors.append("Your specified search parameters were invalid!")

    else:
        form = StatisticsSearchForm(source_id)
    
    return render(request, 'visualization/statistics.html', {
        'errors': errors,
        'form': form,
        'source': source,
        'years': years,
        'label_table': label_table,
        'group_table': group_table,
    })
