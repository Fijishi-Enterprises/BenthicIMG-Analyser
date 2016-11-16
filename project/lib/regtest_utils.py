import pickle
import json
import glob
import csv
import sys

import os.path as osp

from io import BytesIO

from PIL import Image as PILImage

from django.core import management
from django.core.files.base import ContentFile
from django.core.urlresolvers import reverse

from django.conf import settings
from django.test.client import Client
from django.contrib.auth import get_user_model

from test_utils import ClientTest

from images.models import Source, Image
from labels.models import LabelGroup, Label, LabelSet, LocalLabel




class RegressionTest(ClientTest):
    """
    Managment class for vision backend regression tests.
    This class relies on a specific regression test fixture layout.
    """
    
    def __init__(self, source_id, name_suffix):
        """
        Initialize class instance.
        """

        self.client = Client()
        # Create a superuser.
        User = get_user_model()
        if not User.objects.filter(username='superuser').exists():
            management.call_command('createsuperuser',
                '--noinput', username='superuser',
                email='superuser@example.com', verbosity=0)
        self.user = User.objects.get(username='superuser')

        # Create other users.
        for username in [settings.IMPORTED_USERNAME, settings.ROBOT_USERNAME, settings.ALLEVIATE_USERNAME]:
            if not User.objects.filter(username = username).exists():
                user = User(username=username)
                user.save()
        
        # Setup path to source_id fixtures.

        self.source_root = osp.join(settings.REGRESSION_FIXTURES_ROOT, 'sources', 's{}'.format(source_id))
        self.annfile = osp.join(self.source_root, 'imdict.p')
        self.sourcename = 'REGTEST_CUSTOM_SOURCE_{}_{}'.format(source_id, name_suffix)
        self.global_labelfile = osp.join(settings.REGRESSION_FIXTURES_ROOT, 'labels.json')
        self.imfiles =  glob.glob(osp.join(self.source_root, 'imgs', '*'))

        # Create source and labelset.
        self._setup_source()

        # Load annotations to memory and prepre for upload.
        self._make_labelcode_dict()
        self._parse_annotations()

        # Initialize the image counter of how many images have been uploaded.
        self.cur = 0
    
    def upload_all_images(self, with_anns = True):
        """
        Upload all images available in fixtures.
        """
        self.upload_images(len(self.imfiles), with_anns = with_anns)

    def upload_images(self, nbr, with_anns = True):
        """
        Upload INPUT nbr images.
        """
        for i in range(nbr):
            self.upload_image(with_anns = with_anns)

    def upload_image(self, with_anns = True):
        """
        Upload an image.
        """
        if self.cur + 1 == len(self.imfiles):
            print "Already uploaded all images."
            return
        img = self.imfiles[self.cur]
        
        sys.stdout.write(str(self.cur) + ', ')
        sys.stdout.flush()
        
        self.cur += 1
        self._upload_image(img)
        
        if with_anns:
            anns = self.anns[osp.basename(img)]
            self._upload_annotations(osp.basename(img), anns)

    def _setup_source(self):
        """
        Creates source and labelset. Also creates global labels if needed.
        """
        print "Setting up: {}".format(self.sourcename)
        if Source.objects.filter(name = self.sourcename).exists():
            Source.objects.filter(name = self.sourcename).delete()
        
        # Create new source.
        self.source = self.create_source()
        
        # Find all labelnames in exported annotation file.
        f = open(self.annfile, 'r')
        anns = pickle.load(f)
        labellist = set()
        for key in anns.keys():
            for [labelname, row, col] in anns[key][0]:
                labellist.add(labelname)

        # Create global labels if needed                
        self._add_global_labels(labellist)

        # Create labelset for this source.
        labelset = LabelSet()
        labelset.save()
        self.source.labelset = labelset
        self.source.save()
        for name in labellist:
            label = Label.objects.get(name = name)
            LocalLabel(
                global_label = label,
                code = label.default_code,
                labelset = labelset
            ).save()   

    def create_source(self):
        """
        Create a source.
        :param user: User who is creating this source.
        :param name: Source name. "Source <number>" if not given.
        """
        post_dict = dict()
        post_dict.update(self.source_defaults)
        post_dict['name'] = self.sourcename

        self.client.force_login(self.user)
        self.client.post(reverse('source_new'), post_dict)
        self.client.logout()
        return Source.objects.get(name = self.sourcename)

    def _make_labelcode_dict(self):
        """
        Returns a dictionary which maps label names to label code.
        This is needed b/c the upload form needs codes but the fixtures lists
        label names.
        """
        with open(self.global_labelfile) as f:
            (grps, lbls) = json.load(f)
        codedict = dict()
        for lbl in lbls:
            codedict[lbl[0]] = lbl[1]
        self.codedict = codedict
        return

    def _parse_annotations(self):
        """
        Parses exported annotation file and returns a dictionary ready to be uploaded.
        """
        f = open(self.annfile, 'r')
        anns = pickle.load(f)
        newanns = dict()
        for imname in anns.keys():
            newanns[imname] = []
            for [labelname, row, col] in anns[imname][0]:
                labelcode = self.codedict[labelname]
                newanns[imname].append((row, col, labelcode))
        
        self.anns = newanns

    def _add_global_labels(self, labellist):
        """
        Imports all labels and groups from a json file. See 
        "vision_backend/scripts.export_labels_json".
        """
        with open(self.global_labelfile) as f:
            (grps, lbls) = json.load(f)

        for grp in grps:
            self._add_functional_group(grp[0], grp[1])

        for lbl in lbls:
            if lbl[0] in labellist:
                self._add_label(lbl[0], lbl[1], lbl[2])     

    def _add_functional_group(self, name, code):
        """
        Adds functional group to DB.
        """
        if LabelGroup.objects.filter(name = name).count() > 0:
            return
        LabelGroup(
            name = name,
            code = code
        ).save()
        
    def _add_label(self, name, code, group):
        """
        Adds label to DB.
        """
        if Label.objects.filter(name = name).count() > 0:
            return
        Label(
            name = name,
            default_code = code,
            group = LabelGroup.objects.get(name = group)
        ).save()

    def _upload_annotations(self, imfile, anns):
        """
        Annotations on all specified points.
        """

        def preview_anns(csv_file):
            return self.client.post(
                reverse('upload_annotations_preview_ajax', args=[self.source.pk]),
                {'csv_file': csv_file},
            )

        def upload_anns():
            return self.client.post(
                reverse('upload_annotations_ajax', args=[self.source.pk]),
            ) 

        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Row', 'Column', 'Label'])
            for ann in anns:
                writer.writerow([imfile, ann[0], ann[1], ann[2]])
            
            f = ContentFile(stream.getvalue(), name='ann_upload' + '.csv')
            preview_response = preview_anns(f)
            upload_response = upload_anns()

    def _upload_image(self, imfile):
        """
        Upload a data image.
        :param user: User to upload as.
        :param source: Source to upload to.
        :param imfile: path to the image file to upload.
        :return: The new image object.
        """

        def image_to_buffer(imfile):
            """
            Convert imfile to buffer
            """

            filename = osp.basename(imfile)
            filetype = osp.splitext(imfile)[-1]
            
            if filetype.upper() in ['.JPG', '.JPEG']:
                filetype = 'JPEG'
            elif filetype.upper() == '.PNG':
                filetype = 'PNG'

            im = PILImage.open(imfile)

            with BytesIO() as stream:
                im.save(stream, filetype)
                image_file = ContentFile(stream.getvalue(), name=filename)
            return image_file  


        post_dict = dict()        
        post_dict['file'] = image_to_buffer(imfile)

        # Send the upload form
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('upload_images_ajax', kwargs={'source_id': self.source.id}),
            post_dict,
        )
        self.client.logout()

    