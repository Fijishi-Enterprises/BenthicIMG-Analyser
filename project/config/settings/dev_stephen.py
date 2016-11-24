from .base_devserver import *

# Pick one.
from .storage_local import *
# from .storage_s3 import *
# from .storage_regtests import *

MAP_IMAGE_COUNT_TIERS = [5, 20, 50]

MIN_NBR_ANNOTATED_IMAGES = 5
