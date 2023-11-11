from enum import Enum


class Extractors(Enum):
    VGG16 = 'vgg16_coralnet_ver1'
    EFFICIENTNET = 'efficientnet_b0_ver1'
    DUMMY = 'dummy'


# Hard-coded shallow learners for each deep model.
# MLP is the better newer shallow learner, but we stayed with
# LR for the old extractor for backwards compatibility.
CLASSIFIER_MAPPINGS = {
    Extractors.VGG16.value: 'LR',
    Extractors.EFFICIENTNET.value: 'MLP',
    Extractors.DUMMY.value: 'LR',
}
