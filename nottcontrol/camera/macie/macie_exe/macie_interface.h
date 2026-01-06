#include <string>
using std::string;

extern "C" int M_initialize(const char* configFile, bool offline_mode);
extern "C" void M_acquire(const bool no_recon);
extern "C" bool M_initCamera();
extern "C" void M_powerOff();
extern "C" void M_powerOn();
extern "C" void M_getPower();
extern "C" void M_close();