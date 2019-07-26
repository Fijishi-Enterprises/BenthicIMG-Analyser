from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.functional import wraps

from annotations.utils import image_annotation_area_is_editable
from images.models import Source, Image

class ModelViewDecorator():
    """
    Class for instantiating decorators for views.
    Specifically, views that take the id of a model as a parameter.

    :param model_class: The model that the view takes an id parameter of.
    :param meets_requirements: Function that determines whether we've
       met the requirements to show the view normally.
    :param template: Template to show if the requirements weren't met.
    :param get_extra_context: Function that gets extra info (as a dict)
       about the model object. In the case that we must render the
       requirements-not-met template, this extra info is added to the
       rendering context.
    :param default_message: Default message to display on the
       requirements-not-met template.
    """

    def __init__(self, model_class, meets_requirements,
                 template, get_extra_context=None,
                 default_message=None):
        self.model_class = model_class
        self.meets_requirements = meets_requirements
        self.template = template
        self.get_extra_context = get_extra_context
        self.default_message = default_message

    def __call__(self, object_id_view_arg, message=None, ajax=False, **requirements_kwargs):
        def decorator(view_func):
            def _wrapped_view(request, *args, **kwargs):

                if object_id_view_arg not in kwargs:
                    raise ValueError("Argument %s was not passed "
                                     "into view function" % object_id_view_arg)
                object_id = kwargs[object_id_view_arg]

                object = get_object_or_404(self.model_class, pk=object_id)

                if not self.meets_requirements(object, request, **requirements_kwargs):
                    fail_message = message or self.default_message or ""

                    # Ajax: Return a dict with an error field
                    if ajax:
                        return JsonResponse(dict(error=fail_message))

                    # Not Ajax: Render a template
                    context_dict = dict(message=fail_message)
                    if self.get_extra_context:
                        context_dict.update(self.get_extra_context(object))

                    return render(request, self.template, context_dict)

                return view_func(request, *args, **kwargs)
            return wraps(view_func)(_wrapped_view)
        return decorator

def image_get_extra_context(image):
    return dict(
        image=image,
        source=image.source,
    )
def source_get_extra_context(source):
    return dict(
        source=source,
    )

# @image_annotation_area_must_be_editable('image_id')
image_annotation_area_must_be_editable = ModelViewDecorator(
    model_class=Image,
    meets_requirements=lambda image, request: image_annotation_area_is_editable(image),
    template='annotations/annotation_area_not_editable.html',
    get_extra_context=image_get_extra_context,
    default_message="This image's annotation area is not editable, because re-generating points "
                    "would result in loss of data (such as annotations made in the annotation tool, "
                    "or points imported from outside the site)."
    )

# @image_labelset_required('image_id')
image_labelset_required = ModelViewDecorator(
    model_class=Image,
    meets_requirements=lambda image, request: image.source.labelset is not None,
    template='labels/labelset_required.html',
    get_extra_context=image_get_extra_context,
    default_message="You need to create a labelset before you can use this page."
    )

# @source_labelset_required('source_id')
source_labelset_required = ModelViewDecorator(
    model_class=Source,
    meets_requirements=lambda source, request: source.labelset is not None,
    template='labels/labelset_required.html',
    get_extra_context=source_get_extra_context,
    default_message="You need to create a labelset before you can use this page."
)

# @image_visibility_required('image_id')
image_visibility_required = ModelViewDecorator(
    model_class=Image,
    meets_requirements=lambda image, request: image.source.visible_to_user(request.user),
    template='permission_denied.html',
    default_message="Sorry, you don't have permission to view this page."
)

# @source_visibility_required('source_id')
source_visibility_required = ModelViewDecorator(
    model_class=Source,
    meets_requirements=lambda source, request: source.visible_to_user(request.user),
    template='permission_denied.html',
    default_message="Sorry, you don't have permission to view this page."
)

# TODO: Make this even more DRY: just pass in 'admin' instead of Source.PermTypes.ADMIN.code.
# @image_permission_required('image_id', perm=Source.PermTypes.<YOUR_PERMISSION_TYPE_HERE>.code)
image_permission_required = ModelViewDecorator(
    model_class=Image,
    meets_requirements=lambda image, request, perm: request.user.has_perm(perm, image.source),
    template='permission_denied.html',
    default_message="You don't have permission to access this part of this source."
)

# @source_permission_required('source_id', perm=Source.PermTypes.<YOUR_PERMISSION_TYPE_HERE>.code)
source_permission_required = ModelViewDecorator(
    model_class=Source,
    meets_requirements=lambda source, request, perm: request.user.has_perm(perm, source),
    template='permission_denied.html',
    default_message="You don't have permission to access this part of this source."
)


# Version of login_required that can be used on Ajax views.
# @login_required_ajax
def login_required_ajax(view_func):
    def wrapper_func(request, *args, **kwargs):
        if not request.user.is_authenticated:
            # If not signed in, return error response
            return JsonResponse(
                dict(error="You must be signed in to access this function."))
        else:
            # Else, same behavior as calling the view directly
            return view_func(request, *args, **kwargs)
    return wrapper_func
