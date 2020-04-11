import argparse
import sys
import pip
import os
from cStringIO import StringIO



def compare_requirements(mode, reqdir):
	
	current = set(pip_freeze().split('\n'))

	base = read_reqfile(os.path.join(reqdir, 'base.txt'))
	extra = read_reqfile(os.path.join(reqdir, '{}.txt'.format(mode)))
	total_req = base.union(extra)
	print("Extra installed:")
	print_set(current.difference(total_req))
	print("Missing:")
	print_set(total_req.difference(current))


def print_set(_set):
	for member in _set:
		print(member)


def pip_freeze():

	# setup the environment
	backup = sys.stdout

	sys.stdout = StringIO()     # capture output
	pip.main(['freeze'])
	out = sys.stdout.getvalue() # release output

	sys.stdout.close()  # close the stream 
	sys.stdout = backup # restore original stdout

	return out.lower()

def read_reqfile(filename):

	lines = [line.rstrip('\n').lower() for line in open(filename)]
	lines = [line for line in lines if len(line) > 0]
	lines = [line for line in lines if not line[0] == '#']
	lines = [line for line in lines if not line[0] == '-']
	lines = [line for line in lines if not line[0] == ' ']
	lines = [line for line in lines if not line[0] is None]
	return set(lines)



parser = argparse.ArgumentParser(description='Compare pip freeze to coralnet requirements') 
	
parser.add_argument('mode', type=str, help='local or production', choices = ['local', 'production'])

parser.add_argument('reqdir', type=str, help='directory where requirements files live')

args = parser.parse_args()

compare_requirements(args.mode, args.reqdir)