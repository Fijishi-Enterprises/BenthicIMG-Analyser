# VISION BACKEND SETTINGS
# TODO: move to separate settings file.

NEW_CLASSIFIER_TRAIN_TH = 1.1

NEW_CLASSIFIER_IMPROVEMENT_TH = 1.02

MIN_NBR_ANNOTATED_IMAGES = 20

FEATURE_VECTOR_FILE_PATTERN = '{full_image_path}.featurevector'

ROBOT_MODEL_FILE_PATTERN = '{media}/classifiers/{pk}.model'

ROBOT_MODEL_TRAINDATA_PATTERN = '{media}/classifiers/{pk}.traindata'

ROBOT_MODEL_VALDATA_PATTERN = '{media}/classifiers/{pk}.valdata'

ROBOT_MODEL_VALRESULT_PATTERN = '{media}/classifiers/{pk}.valresult'

NBR_SCORES_SCORED_PER_ANNOTATION = 5