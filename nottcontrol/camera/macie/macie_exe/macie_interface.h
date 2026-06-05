#include <string>
using std::string;

extern "C" int M_initialize(const char* configFile, bool offline_mode);
extern "C" bool M_acquire(const bool no_recon);
extern "C" bool M_halt_acquisition();
extern "C" bool M_initCamera();
extern "C" bool M_powerOff();
extern "C" bool M_powerOn();
extern "C" bool M_getPower();
extern "C" bool M_close();
extern "C" bool M_exposure_settings(bool save, int ncoadds, int nseq, int ngroups, int nreads, int ndrops, int nresets);
extern "C" bool M_frame_settings(bool xWindowing, bool yWindowing, int x1, int x2, int y1, int y2);