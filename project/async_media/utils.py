import uuid
from django.core.cache import cache


# We use the cache to track ongoing thumbnail requests.
# We don't use sessions so that anonymous users with cookies off are also
# supported.

# The cache entry expiration time should be longer than the duration of any
# pageful of thumbnail requests. It should also be reasonably short so that
# there's still room for other types of cache entries.
CACHE_EXPIRATION_SECONDS = 10*60

def get_thumbnail_request_status(first_hash):
    cache_key = 'thumbnail_async_status_{fh}'.format(fh=first_hash)
    return cache.get(cache_key)
def set_thumbnail_request_status(first_hash, status_dict):
    cache_key = 'thumbnail_async_status_{fh}'.format(fh=first_hash)
    cache.set(cache_key, status_dict, CACHE_EXPIRATION_SECONDS)
def delete_thumbnail_request_status(first_hash):
    cache_key = 'thumbnail_async_status_{fh}'.format(fh=first_hash)
    cache.delete(cache_key)

def get_thumbnail_url(first_hash, index):
    cache_key = 'thumbnail_async_{first_hash}_{index}'.format(
        first_hash=first_hash, index=index)
    url = cache.get(cache_key)
    cache.delete(cache_key)
    return url
def set_thumbnail_url(first_hash, index, url):
    # We'll just make the polling view responsible for the
    # first thumbnail's hash and the index of the thumbnail set.
    cache_key = 'thumbnail_async_{first_hash}_{index}'.format(
        first_hash=first_hash, index=index)
    cache.set(cache_key, url, CACHE_EXPIRATION_SECONDS)


def set_async_thumbnail_request(name, size, request):
    # Make a hash which identifies a request to generate this thumbnail.
    # Cache the association between the hash and the thumbnail.
    #
    # Later, we will only accept async thumbnail generation requests that
    # provide valid hashes. This prevents us from getting DOSed by
    # arbitrary thumbnail generation requests.
    cache_key = None
    random_hash = None
    while not cache_key:
        random_hash = uuid.uuid4().hex
        cache_key_candidate = 'thumbnail_async_request_{hash}'.format(
            hash=random_hash)
        # If there are no collisions with other ongoing thumbnail requests,
        # then use this hash.
        if cache_key_candidate not in cache \
         and not get_thumbnail_request_status(random_hash):
            cache_key = cache_key_candidate

    # Ensure this user is the same one making the subsequent requests for
    # async thumbnails. We want to make it impossible for a different user
    # (or anonymous user) to access arbitrary thumbnails by guessing hashes.
    user_id = request.user.pk if request.user.is_authenticated() else None

    cache.set(cache_key, (name, size, user_id), CACHE_EXPIRATION_SECONDS)

    return random_hash
