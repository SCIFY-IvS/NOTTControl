#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Basic file manipulation functions used by the NOTT code

This module contains various file functions to...

Example:

To do:
* 
*

Modification history:
* Version 1.0.0: Denis Defrere (KU Leuven) -- denis.defrere@kuleuven.be

"""
__author__ = "Denis Defrere"
__copyright__ = "Copyright 2024, The SCIFY Project"
__credits__ = ["Kwinten Missiaen","Muhammad Salman","Marc-Antoine Martinod"]
__license__ = "GPL"
__version__ = "1.0.0"
__maintainer__ = "Denis Defrere"
__email__ = "denis.defrere@kuleuven.be"
__status__ = "Production"

import pickle
import os

def save_data(data, path, name):
    print('MSG - Save data in:', path+name)
    list_saved_files = [elt for elt in os.listdir(path) if name in elt]
    count_file = len(list_saved_files) + 1
    name_file = name+'_%03d.pkl'%(count_file)
    dbfile = open(path + name_file, 'wb')
    pickle.dump(data, dbfile)
    dbfile.close()