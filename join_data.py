'''
Join sets of dedalus output data.

Usage:
      join_data.py <case>... [--data_type=<data_type> --no-cleanup]

Options:
      --data_type=<data_type>      Type of data to join; if provided join a single data.
      --no-cleanup                 Prevent cleanup operation after join

'''

import os
import sys
import logging
logger = logging.getLogger(__name__)

import dedalus.public
from dedalus.tools  import post

from docopt import docopt

args = docopt(__doc__)

data_dir = args['<case>'][0]
base_path = os.path.abspath(data_dir)+'/'

cleanup = not(args['--no-cleanup'])

logger.info("joining data from Dedalus run {:s}".format(data_dir))

if args['--data_type'] is not None:
    data_types=[args['--data_type']]
else:
    data_types = ['scalar', 'profiles', 'slices', 'coeffs', 'volumes', 'checkpoint']

for data_type in data_types:
    logger.info("merging {}".format(data_type))
    try:
        post.merge_process_files(base_path+data_type, cleanup=cleanup)
    except:
        logger.info("missing {}".format(data_type))
        
logger.info("done join operation for {:s}".format(data_dir))
