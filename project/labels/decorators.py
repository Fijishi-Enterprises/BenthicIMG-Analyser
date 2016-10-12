from lib.decorators import ModelViewDecorator
from .models import Label
from .utils import is_label_editable_by_user


# @label_edit_permission_required('label_id')
label_edit_permission_required = ModelViewDecorator(
    model_class=Label,
    meets_requirements=(
        lambda label, request: is_label_editable_by_user(label, request.user)),
    template='permission_denied.html',
    default_message="You don't have permission to edit this label."
)
