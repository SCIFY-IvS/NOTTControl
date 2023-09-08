# -*- coding: utf-8 -*-
"""
Created on Wed May  3 11:09:31 2023

@author: Kwinten
"""

from PyQt5.QtWidgets import QDialog
from PyQt5.uic import loadUi
from PyQt5.QtCore import Qt
from .infratec_interface import InfratecInterface, Image

class PresetParameter:
    def __init__(self, name, parameter_nr, parameter_type, read=True, write=True):
        self.name = name
        self.parameter_nr = parameter_nr
        self.parameter_type = parameter_type

class ParametersDialog(QDialog):
    
    TYPE_Int32 = 'Int32'
    TYPE_Int64 = 'Int64'
    TYPE_Single = 'Single'
    TYPE_Double = 'Double'
    TYPE_String = 'String'
    TYPE_IdxInt32 = 'IdxInt32'
    TYPE_IdxString = 'IdxString'
    
    def __init__(self, interface):
        super(ParametersDialog, self).__init__()
        self.ui = loadUi('camera/parametersdialog.ui', self)
        self.connectSignalSlots()
        self.interface = interface
        
        self.setup_type_combobox()
        self.setup_presets_combobox()
    
    def setup_type_combobox(self):
        self.ui.cb_parametertype.addItem(self.TYPE_Int32)
        self.ui.cb_parametertype.addItem(self.TYPE_Int64)
        self.ui.cb_parametertype.addItem(self.TYPE_Single)
        self.ui.cb_parametertype.addItem(self.TYPE_Double)
        self.ui.cb_parametertype.addItem(self.TYPE_String)
        self.ui.cb_parametertype.addItem(self.TYPE_IdxInt32)
        self.ui.cb_parametertype.addItem(self.TYPE_IdxString)
    
    def setup_presets_combobox(self):
        parameters = [
            PresetParameter('Framerate_Hz', 240, self.TYPE_Single)
        ]
        
        
        self.ui.cb_presets.addItem('')
        for par in parameters:
            self.ui.cb_presets.addItem(par.name, userData = par)
        
        self.ui.cb_presets.currentIndexChanged.connect(self.selected_preset_changed)
    
    def connectSignalSlots(self):
        self.ui.button_get.clicked.connect(self.get_parameter)
        self.ui.button_set.clicked.connect(self.set_parameter)
    
    def selected_preset_changed(self):
        selectedText = self.ui.cb_presets.currentText()
        if selectedText == '':
            #clear values
            self.ui.edit_param_nr.clear()
            self.ui.edit_param_value.clear()
        else:
            selectedParam = self.ui.cb_presets.currentData()
            self.ui.edit_param_nr.setText(str(selectedParam.parameter_nr))
            print(selectedParam.parameter_type)
            index = self.ui.cb_parametertype.findText(selectedParam.parameter_type, Qt.MatchFixedString)
            if index >=0:
                self.ui.cb_parametertype.setCurrentIndex(index)
    
    def get_parameter(self):
        parameter_nr = int(self.ui.edit_param_nr.text())
        parameter_type = self.ui.cb_parametertype.currentText()
        result = -1
        match parameter_type:
            case self.TYPE_Int32:
                result = self.interface.getparam_int32(parameter_nr)
            case self.TYPE_Int64:
                result = self.interface.getparam_int64(parameter_nr)
            case self.TYPE_Single:
                result = self.interface.getparam_single(parameter_nr)
            case self.TYPE_Double:
                result = self.interface.getparam_double(parameter_nr)
            case self.TYPE_String:
                result = self.interface.getparam_string(parameter_nr)
        #TOOD: finish match statement
        
        self.ui.edit_param_value.setText(str(result))
        self.ui.label_feedback.setText('Parameter get succesful')
    
    def set_parameter(self):
        parameter_type = self.ui.cb_parametertype.currentText()
        parameter_nr = int(self.ui.edit_param_nr.text())
        value = self.ui.edit_param_value.text()
        
        match parameter_type:
            case self.TYPE_Int32:
                self.interface.setparam_int32(parameter_nr, int(value))
            case self.TYPE_Int64:
                self.interface.setparam_int64(parameter_nr, int(value))
            case self.TYPE_Single:
                self.interface.setparam_single(parameter_nr, float(value))
            case self.TYPE_Double:
                self.interface.setparam_double(parameter_nr, float(value))
            case self.TYPE_String:
                self.interface.setparam_string(parameter_nr, value)
        #TODO finish match statement
        
        self.ui.edit_param_value.clear()
        self.ui.label_feedback.setText('Parameter set succesful')
