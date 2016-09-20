from django.shortcuts import render
from images.models import Source
from images.utils import source_robot_status

# Create your views here.
def backend_overview(request):

    laundry_list = []
    for source in Source.objects.filter():
        laundry_list.append(source_robot_status(source.id))
    timestr = ""

    laundry_list = sorted(laundry_list, key=lambda k: k['need_attention']*k['id'])[::-1]
    
    return render(request, 'vision_backend/overview.html', {
        'laundry_list': laundry_list,
        'timestr': timestr,
    })