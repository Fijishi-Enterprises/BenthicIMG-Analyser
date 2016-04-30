# task_helpers.py contains SYSTEM SPECIFIC helper functions for tasks.
# For production environments, these are typically calls to an
# outside program like Matlab.  For development environments,
# these are typically light scripts that do the minimum file manipulations
# required by the task.
#
# Because task_helpers.py is system specific, it should not be added
# to the Git repository.  Only this file (which is not imported by
# anything, but merely serves as an example) should be in the Git
# repository.
import json
import operator
import os
import random

from django.conf import settings

join_processing_root = lambda *p: os.path.join(settings.PROCESSING_ROOT, *p)
MODEL_DIR = join_processing_root("images/models/")


def coralnet_preprocessImage(imageFile, preprocessedImageFile, preprocessParameterFile, ssFile , logFile, errorLogfile):
    # The Preprocessing step prepares the image for feature making.
    pass

def coralnet_makeFeatures(preprocessedImageFile, featureFile, rowColFile, ssFile, featureExtractionParameterFile, logFile, errorLogfile):
    # The Feature file encodes the visual features around each point.

    # The feature file has one line per point. Each line has at least two
    # tokens separated by whitespace.
    row_col_f = open(rowColFile)
    feature_f = open(featureFile, 'w')

    for point_num, line in enumerate(row_col_f, 1):

        line = line.strip()
        if line == '':
            continue

        feature_f.write('{point_num} {point_num}\n'.format(point_num=point_num))

    row_col_f.close()
    feature_f.close()


def coralnet_classify(featureFile, modelFile, labelFile, logFile, errorLogfile):
    # The label file is the result of classification: what each point is labelled as.
    # From the feature file, we get information about the points.
    # From the model file, we figure out how to label a point given its features.
    #
    # The model file needs to be made manually or by a separate program; it is not
    # made by any tasks.  The model file also needs to be set as the path_to_model of
    # the Robot that's being used.


    # The feature file has one line per point. Each line has at least two
    # tokens separated by whitespace.

    feature_f = open(featureFile)
    num_of_points = 0

    for line in feature_f:

        line = line.strip()
        if line == '':
            continue

        num_of_points += 1

    feature_f.close()


    # From the model-describing JSON file, the only thing we really need is
    # the list of label ids.

    model_json_filepath = '{model_base_path}.meta.json'.format(
        model_base_path=modelFile
    )
    model_f = open(model_json_filepath)
    json_obj = json.load(model_f)
    label_ids = json_obj['labelMap']

    model_f.close()


    # Label probabilities file.
    # Example:
    # labels 2 3 4 1 5 13 6 7 8
    # 5 0.0500984 0.13629 0.208848 0.0387356 0.326232 0.0506014 0.0337545 0.122562 0.0328777
    # 5 0.0393132 0.104304 0.121394 0.0282059 0.51007 0.0277023 0.0255941 0.123775 0.0196418
    # 5 0.0429154 0.130267 0.152167 0.0312479 0.424764 0.0349074 0.0257661 0.134511 0.0234539
    # ... (one line of numbers for each point)
    #
    # Labels file.
    # The label file should have one label id per line, with each line
    # corresponding to one point of the image.

    prob_f = open(labelFile+'.prob', 'w')
    label_f = open(labelFile, 'w')

    labels_line = ' '.join(['labels']+label_ids)
    prob_f.write(labels_line+'\n')

    # http://stackoverflow.com/questions/2171074/generating-a-probability-distribution
    for i in range(num_of_points):
        rands = [random.random() for label_id in label_ids]
        total_of_rands = sum(rands)
        probs = [round(r/total_of_rands, 7) for r in rands]
        max_prob_label_id = max(zip(label_ids, probs), key=operator.itemgetter(1))[0]

        probs_line = ' '.join([max_prob_label_id]+[str(p) for p in probs])
        prob_f.write(probs_line+'\n')

        label_f.write(str(max_prob_label_id)+'\n')

    prob_f.close()
    label_f.close()


def coralnet_trainRobot(modelPath, oldModelPath, pointInfoPath, fileNamesPath, workDir, logFile, errorLogfile):

    # modelPath is the path the the new robotMode, the oldModelpath is the path to the previous. pointInfoPath contains info about each point, label and fromfile. filenamesPath is a list of the feature fiels. workDir is a temp directory for matlab to work in.


    # From the point info file, get all of the possible label ids.
    label_ids = set()
    point_info_f = open(pointInfoPath)

    for line in point_info_f:
        line = line.strip()
        image_num, point_num, label_id = line.split(', ')
        label_ids.add(label_id)

    point_info_f.close()


    # The JSON file describing the model.
    model_json_filepath = '{model_base_path}.meta.json'.format(
        model_base_path=modelPath
    )
    model_f = open(model_json_filepath, 'w')
    obj = {
        'final': {
            'trainData': {
                'labelHist': {
                    'org': 20
                }
            }
        },
        'hp': {
            'estPrecision': 0.2941183535,
            'gridStats': {
                # cmOpt can be a direct child of gridStats,
                # or a child of the last child of gridStats
                'cmOpt': [random.choice(range(10))
                          for i in range(len(label_ids)*len(label_ids))],
            },
        },
        'labelMap': list(label_ids),
        'totalRuntime': 9000.192592,
    }

    json.dump(obj, model_f)

    model_f.close()