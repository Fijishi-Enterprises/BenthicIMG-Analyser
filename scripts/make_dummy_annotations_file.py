import glob
import os
import numpy as np
import random
def make_dummy_annotations_file(imgdir, filename):
	with open(filename, 'w') as f:
		f.write('{}, {}, {}, {}\n'.format('Name', 'Row', 'Column', 'Label'))
		for image in glob.glob(os.path.join(imgdir, '*.jpg')):
			for i in range(10):
				if random.random() < .5:
					f.write('{}, {}, {}, {}\n'.format(os.path.basename(image), np.random.randint(10, 500), np.random.randint(10, 500), 'sdf'))
				else:
					f.write('{}, {}, {}, {}\n'.format(os.path.basename(image), np.random.randint(10, 500), np.random.randint(10, 500), 'sdfddd'))
