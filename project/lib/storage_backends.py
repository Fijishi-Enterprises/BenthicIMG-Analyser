from __future__ import unicode_literals
from abc import ABCMeta
from distutils.dir_util import copy_tree
import os
from pathlib2 import Path
import posixpath
import random
import shutil
import six
import string
import tempfile

from django.conf import settings
from django.core.files.storage import DefaultStorage, FileSystemStorage
from storages.backends.s3boto import S3BotoStorage

from .exceptions import FileStorageUsageError


# Abstract class
@six.add_metaclass(ABCMeta)
class StorageManager(object):

    def copy_dir(self, src, dst):
        """
        Copy a directory recursively from `src` to `dst`. Both should be
        absolute paths / paths from bucket root.
        """
        raise NotImplementedError

    def create_settings_override(self, temp_dir):
        """
        :param temp_dir: Absolute path / path from bucket root of the temp dir
          that we're creating a settings override for.
        :return: A dict of file storage settings, allowing us to use temp_dir
          for storage. Can be used in an override_settings decorator or
          similar.
        """
        raise NotImplementedError

    def create_temp_dir(self):
        """
        Create a directory for temporary files, and return its absolute path /
        path from bucket root.
        """
        raise NotImplementedError

    def _remove_dir(self, dir_to_remove):
        """Remove the directory at the given path."""
        raise NotImplementedError

    def remove_temp_dir(self, dir_to_remove):
        """
        Check that a directory is most likely a temporary directory, then
        remove it.
        """
        # Sanity check to prevent data loss.
        parts = [part.lower() for part in Path(dir_to_remove).parts]
        # If there are other possible temporary-directory name patterns,
        # add them here.
        if not ('tmp' in parts or 'temp' in parts):
            raise FileStorageUsageError(
                "The dir path doesn't contain a 'tmp' or 'temp' dir"
                " (case insensitive), so we're not sure if it's a temporary"
                " directory or not.")

        self._remove_dir(dir_to_remove)


class StorageManagerS3(StorageManager):

    def copy_dir(self, src, dst):
        s3_root_storage = get_s3_root_storage()

        # List directories and files in this directory.
        subdirs, filenames = s3_root_storage.listdir(src)
        for filename in filenames:
            # Copy the file from src to dst.
            f = s3_root_storage.open(s3_root_storage.path_join(src, filename))
            s3_root_storage.save(s3_root_storage.path_join(dst, filename), f)
        for subdir in subdirs:
            # Copy the subdir from src to dst using recursion.
            self.copy_dir(
                s3_root_storage.path_join(src, subdir),
                s3_root_storage.path_join(dst, subdir))

    def create_settings_override(self, temp_dir):
        filepath_settings_override = dict()
        storage = DefaultStorage()

        filepath_settings_override['AWS_LOCATION'] = \
            storage.path_join(temp_dir, settings.AWS_S3_MEDIA_SUBDIR)

        filepath_settings_override['MEDIA_URL'] = \
            posixpath.join(
                'https://{domain}'.format(domain=settings.AWS_S3_DOMAIN),
                temp_dir,
                settings.AWS_S3_MEDIA_SUBDIR)

        return filepath_settings_override

    def create_temp_dir(self):
        s3_root_storage = get_s3_root_storage()

        # Doubtful that S3 has any concept of temporary directories, since
        # directories are already kind of a nebulous concept in S3: they
        # can't be created manually, but they automatically get created as you
        # save new filepaths, and automatically get deleted when emptied.
        #
        # So, we'll just create any old directory and attempt to clean it up
        # later. We just have to identify a free directory name to create files
        # in.
        #
        # get_available_name() already adds a suffix as necessary
        # (like `_123abCD`) to avoid clashing with an existing name.
        # However, it's still possible that this directory gets taken by
        # a different thread (e.g. when running tests in parallel), or even by
        # a subsequent temp-dir call in the same thread (e.g. class temp dir
        # followed by method temp dir) if we don't create a file in this dir
        # immediately.
        # So, we also add our own suffix here to minimize chance of conflict.
        suffix = ''.join([
            random.choice(string.digits + string.ascii_letters)
            for _ in range(10)])
        dir_path = 'tmp/tmp_' + suffix
        return s3_root_storage.get_available_name(dir_path)

    def _remove_dir(self, dir_to_remove):
        # List directories and files in this directory.
        s3_root_storage = get_s3_root_storage()
        subdirs, filenames = s3_root_storage.listdir(dir_to_remove)

        for filename in filenames:
            # Remove the file.
            s3_root_storage.delete(
                s3_root_storage.path_join(dir_to_remove, filename))
        for subdir in subdirs:
            # Delete the subdir using recursion.
            self._remove_dir(
                s3_root_storage.path_join(dir_to_remove, subdir))


class StorageManagerLocal(StorageManager):

    def copy_dir(self, src, dst):
        copy_tree(src, dst)

    def create_settings_override(self, temp_dir):
        filepath_settings_override = dict()
        storage = DefaultStorage()

        filepath_settings_override['MEDIA_ROOT'] = \
            storage.path_join(temp_dir, 'media')

        return filepath_settings_override

    def create_temp_dir(self):
        # We'll use an OS-designated temp dir.
        return tempfile.mkdtemp()

    def _remove_dir(self, dir_to_remove):
        shutil.rmtree(dir_to_remove)


class MediaStorageS3(S3BotoStorage):
    """
    S3-bucket storage backend.
    Storage root defaults to the AWS_LOCATION directory.
    """
    def __init__(self, **kwargs):
        # django-storages's S3BotoStorage is implemented a bit differently from
        # Django's FileSystemStorage: it initializes the location attribute to
        # the appropriate setting on the class definition level, rather than in
        # __init__(). This means S3BotoStorage might not pick up changes to
        # settings, which might occur when unit testing for example.
        #
        # To allow S3 storage to pick up on settings changes, we'll pass a
        # default `location` kwarg equal to the appropriate setting.
        if 'location' not in kwargs:
            kwargs['location'] = settings.AWS_LOCATION
        super(MediaStorageS3, self).__init__(**kwargs)

    def exists(self, name):
        # Check for existing file. This doesn't work on dirs.
        if super(MediaStorageS3, self).exists(name):
            return True

        # Check for existing dir (Django's local storage class also returns
        # True on dirs). We do this by checking if listdir() returns any
        # dirs or files.
        dirs, files = self.listdir(name)
        return bool(dirs or files)

    def get_available_name(self, name, max_length=None):
        available_name = super(MediaStorageS3, self).get_available_name(
            name, max_length=max_length)

        # Django's suffix-appending code uses os.path.join(), so if we're
        # running on Windows, the path will end up with backslash separators.
        # We want to change the backslashes to forward slashes, since S3 uses
        # forward slashes.
        # However, on the off chance that a dir/file name legitimately uses a
        # backslash, we'll only make this correction on Windows.
        if os.name == 'nt':
            available_name = available_name.replace('\\', '/')

        return available_name

    @staticmethod
    def path_join(*args):
        # For S3 paths, we join with forward slashes.
        return posixpath.join(*args)


class MediaStorageLocal(FileSystemStorage):
    """
    Local-filesystem storage backend.
    Storage root defaults to MEDIA_ROOT.
    """
    @staticmethod
    def path_join(*args):
        # For local storage, we join paths depending on the OS rules.
        return os.path.join(*args)


def get_s3_root_storage():
    """
    Returns an S3 storage backend which accepts operations throughout an
    entire bucket, rather than only within a settings-specified directory.
    """
    # S3 storage's __init__() accepts kwargs to override default attributes.
    # `location` is the path from the bucket root which will be used as the
    # storage root. We want to use bucket root as storage root, so we pass ''.
    return MediaStorageS3(location='')


def get_storage_manager():
    if settings.DEFAULT_FILE_STORAGE == 'lib.storage_backends.MediaStorageS3':
        return StorageManagerS3()
    elif settings.DEFAULT_FILE_STORAGE \
            == 'lib.storage_backends.MediaStorageLocal':
        return StorageManagerLocal()
    else:
        raise FileStorageUsageError("Unrecognized storage class.")
