# -*- coding: utf-8 -*-
"""
Created on Tue Nov 15 17:03:06 2022

@author: Kwinten
"""

import sys
import os
import ctypes,_ctypes

# infratec packages
# try importing as namespace package
try:
    from IRBGrab import irbgrab as irbg
    from IRBGrab import hirbgrab as hirb
    print('namespace-package import')
except (ImportError, ModuleNotFoundError):
    print('directory import')
    # old syspath.append version
    sys.path.append(r'D:\Python_Entwicklertools\IRBGrab')
    sys.path.append(r'D:\Python_Entwicklertools\analyseFunctions') 
    import camera.irbgrab as irbg
    import camera.hirbgrab as hirb

class InfratecInterface:
    def __init__(self):
        self.load_dll()
        self.create_device()
        

    def load_dll(self):
        self.irbgrab_dll = irbg.getDLLHandle()
        self.irbgrab_object=irbg.irbgrab_obj(self.irbgrab_dll)
        inits=self.irbgrab_object.isinit()
        if inits!=0:   
            #verfügbare geräte anzeigen
            res=self.irbgrab_object.availabledevices()
            if res[0]=='0x10000001': 
                self.devices = res[1]
                print('dll loaded')
            else: 
                print('load dll failed')
                self.devices = []
        else: print('load dll failed')
        
    def free_dll(self):
        try:
            del self.irbgrab_object #Objekt löschen
            if 'win' in os.name or 'nt' in os.name: 
                _ctypes.FreeLibrary( self.irbgrab_dll._libraryhandle) #DLL löschen
            else:
                _ctypes.dlclose(self.irbgrab_dll._libraryhandle) 
            del self.irbgrab_dll
            print('Free DLL Done')
            return True
        except:
            print('Free DLL Failed')
            return False
        
    def create_device(self):
        nr_device= 0
        if len(self.devices) > 0: 
            res=self.irbgrab_object.create(nr_device,'')
            if hirb.TIRBG_RetDef[res]=='Success':
                res=self.irbgrab_object.search()
                success=False
                if hirb.TIRBG_RetDef[res[0]]=='Success':
                    if res[1]!=0:
                        success=True
                        self.searchstrings=self.irbgrab_object.get_search_strings()
                        #for i in self.searchstrings: self.control_list[11][0].addItem(i)
                    else: print('No Device Available!')
                elif hirb.TIRBG_RetDef[res[0]]=='NotSupported': success=True #für Simulator                   
                else: print('search error: '+hirb.TIRBG_RetDef[res[0]])
                if success:
                    print('Done')
            else: print('create error: '+hirb.TIRBG_RetDef[res])
        else: print('No Device DLL Available!')
        
    def free_device(self):
        res=self.irbgrab_object.free()
        if hirb.TIRBG_RetDef[res]=='Success':
            print('Free device Done')
            return True
        else: print('Failed')
        return False
        
    def connect(self, callback, context):
        # known bug comes back with an error. res=self.irbgrab_object.get_state() 
        # workaround for this version is to simply set to irbg.TIRBG_RetDef[res]=='Running' and ignore getstate
        res='0x20000004'
        if hirb.TIRBG_RetDef[res]=='Running' or hirb.TIRBG_RetDef[res]=='NotSupported':
            if len(self.searchstrings)!=0:
                cam_nr= 0 # self.control_list[11][0].currentIndex()
                res=self.irbgrab_object.connect(self.searchstrings[cam_nr]) 
            else:
                res=self.irbgrab_object.connect('')
            if hirb.TIRBG_RetDef[res]=='Success':
                res=self.irbgrab_object.startgrab(0) #hier noch abfrage des StreamIndex????
                if hirb.TIRBG_RetDef[res]=='Success':
                    #Let image capture be 'gated' by the trigger: only capture images if the input trigger is high
                    
                    # res = self.irbgrab_object.setparam_int32(342, 1) #IRBG_PARAM_Trigger_GateIdx, connect to Camera In 1
                    # if not hirb.TIRBG_RetDef[res]=='Success':
                    #     print('set parameter IRBG_PARAM_Trigger_GateIdx failed: ' + hirb.TIRBG_RetDef[res])
                    # print('set parameter IRBG_PARAM_Trigger_GateIdx success')
                    # res = self.irbgrab_object.getparam_int32(340)
                    # if hirb.TIRBG_RetDef[res[0]]=='Success':
                    #     print(str(res[1]))
                    
                    # res = self.irbgrab_object.getparam_idx_string(341, 0)
                    # if hirb.TIRBG_RetDef[res[0]]=='Success':
                    #     print(res[1])
                    # res = self.irbgrab_object.getparam_idx_string(341, 1)
                    # if hirb.TIRBG_RetDef[res[0]]=='Success':
                    #     print(res[1])
                    # res = self.irbgrab_object.getparam_idx_string(341, 2)
                    # if hirb.TIRBG_RetDef[res[0]]=='Success':
                    #     print(res[1])
                    # res = self.irbgrab_object.getparam_idx_string(341, 3)
                    # if hirb.TIRBG_RetDef[res[0]]=='Success':
                    #     print(res[1])
                        
                    res=self.irbgrab_object.set_callback_func(callback,context)
                    if hirb.TIRBG_RetDef[res]=='Success':
                        print('Done')
                        return True
                    else:  print('set callback error: '+hirb.TIRBG_RetDef[res])
                else:  print('startgrab error: '+hirb.TIRBG_RetDef[res])
            else: print('connect error: '+hirb.TIRBG_RetDef[res])
        else: print('state error: '+hirb.TIRBG_RetDef[res]) 
        
        return False
        
    def disconnect(self):
        res=self.irbgrab_object.stopgrab(0)
        if hirb.TIRBG_RetDef[res]=='Success':
            res=self.irbgrab_object.disconnect()
            if hirb.TIRBG_RetDef[res]=='Success':
                print('Disconnected done')
                return True
            else: print('disconnect error: '+hirb.TIRBG_RetDef[res]) 
        else:  print('stopgrab error: '+hirb.TIRBG_RetDef[res])
        return False
    
    def get_max_digital_value(self):
        #Little hack: we need the pointer to be set, but don't need the image right now
        #Maybe should be improved later
        self.irbgrab_object.get_data_easy_noFree(2)
                
        values = self.irbgrab_object.get_digital_values()
        
        if hirb.TIRBG_RetDef[values[0]] == 'Success':
            maximum = values[2]
        else:
            print('Error when getting digital values: {}'.format(hirb.TIRBG_RetDef[values[0]]))
            maximum = -1
        
        self.irbgrab_object.free_mem()
        
        return maximum
    
    def get_image(self):
        return Image(self.irbgrab_object)
    
    def extract_parameter_result(self, res):
        if hirb.TIRBG_RetDef[res[0]]=='Success':
            return res[1]
        else:
            raise Exception(hirb.TIRBG_RetDef[res])
    
    def getparam_int32(self, number):
        res = self.irbgrab_object.getparam_int32(number)
        return self.extract_parameter_result(res)
    
    def setparam_int32(self, number, value):
        res = self.irbgrab_object.setparam_int32(number, value)
        
        if hirb.TIRBG_RetDef[res]=='Success':
            return
        else: 
            raise Exception(hirb.TIRBG_RetDef[res]) 
            
    def getparam_int64(self, number):
        res = self.irbgrab_object.getparam_int64(number)
        return self.extract_parameter_result(res)
        
    def setparam_int64(self, number, value):
        res = self.irbgrab_object.setparam_int64(number, value)
        
        if hirb.TIRBG_RetDef[res]=='Success':
            return
        else: 
            raise Exception(hirb.TIRBG_RetDef[res]) 
        
    def getparam_double(self, number):
        res = self.irbgrab_object.getparam_double(number)
        return self.extract_parameter_result(res)
    
    def setparam_double(self, number, value):
        res = self.irbgrab_object.setparam_double(number, value)
        
        if hirb.TIRBG_RetDef[res]=='Success':
            return
        else: 
            raise Exception(hirb.TIRBG_RetDef[res]) 
    
    def getparam_single(self, number):
        res = self.irbgrab_object.getparam_single(number)
        return self.extract_parameter_result(res)
    
    def setparam_single(self, number, value):
        res = self.irbgrab_object.setparam_single(number, value)
        
        if hirb.TIRBG_RetDef[res]=='Success':
            return
        else: 
            raise Exception(hirb.TIRBG_RetDef[res]) 
    
    def getparam_string(self, number):
        res = self.irbgrab_object.getparam_string(number)
        return self.extract_parameter_result(res)
    
    def setparam_string(self, number, astring):
        res = self.irbgrab_object.setparam_string(number, astring)
        
        if hirb.TIRBG_RetDef[res]=='Success':
            return
        else: 
            raise Exception(hirb.TIRBG_RetDef[res]) 
    
    def getparam_idx_int32(self, number, index):
        res = self.irbgrab_object.getparam_idx_int32(number, index)
        return self.extract_parameter_result(res)
        
    def setparam_idx_int32(self, number, index, value):
        res = self.irbgrab_object.setparam_idx_int32(number, index, value)
        
        if hirb.TIRBG_RetDef[res]=='Success':
            return
        else: 
            raise Exception(hirb.TIRBG_RetDef[res]) 

    def getparam_idx_string(self, number, index):
        res = self.irbgrab_object.getparam_idx_string(number, index)
        return self.extract_parameter_result(res)
    
    def setparam_idx_string(self, number, index, string):
        res = self.irbgrab_object.setparam_idx_string(number, index, string)
        
        if hirb.TIRBG_RetDef[res]=='Success':
            return
        else: 
            raise Exception(hirb.TIRBG_RetDef[res]) 
    
class Image:
    def __init__(self, irbgrab):
        self._irbgrab = irbgrab
    
    def __enter__(self):
        self.image_data = self._irbgrab.get_data_easy_noFree(2)
        return self
        
    def __exit__(self, *args):
        self._irbgrab.free_mem()
    
    def get_max_digital_value(self):
        values = self._irbgrab.get_digital_values()
        
        if hirb.TIRBG_RetDef[values[0]] == 'Success':
            maximum = values[2]
        else:
            print('Error when getting digital values: {}'.format(hirb.TIRBG_RetDef[values[0]]))
            maximum = -1
        
        return maximum

    def get_timestamp(self):
        res = self._irbgrab.get_timestamp()
        
        if hirb.TIRBG_RetDef[res[0]] == 'Success':
            timestamp = res[1]
        else:
            print('Error when getting timestamp: {}'.format(hirb.TIRBG_RetDef[res[0]]))
            return -1
        
        return timestamp.value

    def get_image_data(self):
        if hirb.TIRBG_RetDef[self.image_data[0]] != 'Success':
            print('Error getting image data')
        return self.image_data[1]
    
        