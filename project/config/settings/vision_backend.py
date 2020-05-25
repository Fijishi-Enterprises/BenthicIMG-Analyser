# How many more annotated images are required before we try to train a new classifier.
NEW_CLASSIFIER_TRAIN_TH = 1.1

# How much better than previous classifiers must a new one be in order to get accepted.
NEW_CLASSIFIER_IMPROVEMENT_TH = 1.01

# These many must be annotated before a first classifier is trained.
MIN_NBR_ANNOTATED_IMAGES = 20

# Naming schemes
FEATURE_VECTOR_FILE_PATTERN = '{full_image_path}.featurevector'

ROBOT_MODEL_FILE_PATTERN = 'classifiers/{pk}.model'

ROBOT_MODEL_TRAINDATA_PATTERN = 'classifiers/{pk}.traindata'

ROBOT_MODEL_VALDATA_PATTERN = 'classifiers/{pk}.valdata'

ROBOT_MODEL_VALRESULT_PATTERN = 'classifiers/{pk}.valresult'

# This indicates the max number of scores we store per point.
NBR_SCORES_PER_ANNOTATION = 5

# This is the number of epochs we request the SGD solver to take over the data.
NBR_TRAINING_EPOCHS = 10

# This should always be false except for certain unit-test situations.
FORCE_NO_BACKEND_SUBMIT = False
