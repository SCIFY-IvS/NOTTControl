#include "macie_interface.h"
#include <stdio.h>
#include <string>
#include "macie_lib.h"
#include "MacieMain.h"
#include <iostream>
#include "macie.h"


string _configFile = "";
MACIE_Settings *_ptUserData;

extern "C" int M_initialize(const char* configFile, bool offline_mode)
{
    string cfgFile = string(configFile);
    printf("Calling initialize, configfile %s, offline_mode %d \n", configFile, offline_mode);
    _configFile = cfgFile;
    _ptUserData = new MACIE_Settings;
    int ret = initialize(cfgFile, _ptUserData);
    if(offline_mode)
    {
        toggle_offline_testing(true, _ptUserData);
    }
    return ret;
}
extern "C" void M_acquire(const bool no_recon)
{
    std::cout << "Calling acquire" << std::endl;;
    std::cout << no_recon;
    acquire(no_recon, _ptUserData);
    return;
}

extern "C" bool M_initCamera()
{
    std::cout << "Calling initCamera" << std::endl;;
    if(_configFile.empty()){
        std::cout << "Init failed, config file not set" << std::endl;;
        return false;
    }
    return InitCamera(_configFile, MACIE_GigE, _ptUserData);
}

extern "C" void M_powerOff()
{
    std::cout << "Calling powerOff" << std::endl;;
    SetPowerASIC(_ptUserData, false);
}
extern "C" void M_powerOn()
{
    std::cout << "Calling powerOn" << std::endl;;
    SetPowerASIC(_ptUserData, true);
}

extern "C" void M_getPower()
{
    std::cout << "Calling getPower" << std::endl;
    bool pArr[MACIE_PWR_CTRL_SIZE];
    GetPower(_ptUserData, pArr);
}

extern "C" void M_close()
{
    std::cout << "Calling close" << std::endl;
    SetPowerASIC(_ptUserData, false);
    free_resources(_ptUserData);
}