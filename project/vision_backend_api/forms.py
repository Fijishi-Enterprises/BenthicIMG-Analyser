from __future__ import unicode_literals

from api_core.forms import (
    validate_array, validate_hash, validate_integer, validate_string)


def validate_deploy(post_data):
    """
    post_data is a JSON-loaded Python structure (such as a dict).
    In order to validate, it should meet the deploy spec, which is based on
    the jsonapi.org spec. Example:

    dict(
        data=[
            dict(
                type='image',
                attributes=dict(
                    url='URL 1',
                    points=[
                        dict(row=10, column=10),
                        dict(row=20, column=5),
                    ])),
            dict(
                type='image',
                attributes=dict(
                    url='URL 2',
                    points=[
                        dict(row=10, column=10),
                    ])),
        ]
    )

    If any validations fail, an ApiRequestDataError is raised.
    Returns a simpler structure, a list of the 'attributes' dicts.
    """
    validate_hash(post_data, [], expected_keys=['data'])
    # max_length is the max number of images we accept in a single request.
    validate_array(
        post_data['data'], ['data'], check_non_empty=True, max_length=100)

    for image_index, image_spec in enumerate(post_data['data']):

        img_json_path = ['data', image_index]

        validate_hash(
            image_spec, img_json_path, expected_keys=['type', 'attributes'])

        validate_string(
            image_spec['type'], img_json_path + ['type'], equal_to='image')
        validate_hash(
            image_spec['attributes'], img_json_path + ['attributes'],
            expected_keys=['url', 'points'])

        # TODO: Check that this is a valid URL?
        validate_string(
            image_spec['attributes']['url'],
            img_json_path + ['attributes', 'url'])
        # max_length is the max number of points we accept for a single image.
        validate_array(
            image_spec['attributes']['points'],
            img_json_path + ['attributes', 'points'],
            check_non_empty=True, max_length=1000)

        for pt_index, point in enumerate(image_spec['attributes']['points']):

            pt_json_path = img_json_path + ['attributes', 'points', pt_index]

            validate_hash(point, pt_json_path, expected_keys=['row', 'column'])

            validate_integer(
                point['row'], pt_json_path + ['row'], min_value=0)
            validate_integer(
                point['column'], pt_json_path + ['column'], min_value=0)

    return [image_spec['attributes'] for image_spec in post_data['data']]
