#pragma once
#include "TcServices.h"

#define LATITUDE -0.429838786	// [rad] Paranal
#define LONGITUDE 1.228795511	// [rad] Paranal



extern void astroSplitHms(double angle, double *h, double *m, double *s);
extern double astroHms2rad(double angle);
extern double astroDms2rad(double angle);
extern double astroRad2Hms(double angle);
extern double astroRad2Dms(double angle);