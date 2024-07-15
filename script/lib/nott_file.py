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