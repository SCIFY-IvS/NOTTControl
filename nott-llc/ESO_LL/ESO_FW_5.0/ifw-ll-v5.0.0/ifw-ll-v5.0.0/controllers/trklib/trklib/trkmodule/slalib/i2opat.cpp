#include "../TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaI2opat ( double utc, IOpars *ioprms )
/*
**  - - - - - - - - - -
**   s l a I 2 o p a t
**  - - - - - - - - - -
**
**  Recompute the Earth rotation angle in the CIRS to observed place
**  star-independent parameter structure.
**
**  Given:
**
**     utc    double  UTC date/time (modified Julian Date, JD-2400000.5)
**                    (see slaI2opa for comments on leap seconds)
**
**     ioprms IOpars* star-independent CIRS-to-observed parameters:
**      along     double    longitude + s' + dERA(dut) (radians)
**      phi       double    geodetic latitude (radians)
**      hm        double    height above sea level (meters)
**      xpl       double    polar motion xp wrt local meridian (radians)
**      ypl       double    polar motion yp wrt local meridian (radians)
**      sphi      double    sine of geodetic latitude
**      cphi      double    cosine of geodetic latitude
**      diurab    double    magnitude of diurnal aberration vector
**      p         double    pressure (mb,hPa)
**      tk        double    ambient temperature (K)
**      rh        double    relative humidity (0-1)
**      tlr       double    tropospheric lapse rate (K per meter)
**      wl        double    wavelength (micron) or minus frequency (GHz)
**      refa      double    refraction constant A (radians)
**      refb      double    refraction constant B (radians)
**      eral      double    "local" Earth Rotation Angle (radians)
**
**  Returned:
**
**     ioprms IOpars*   star-independent CIRS-to-observed parameters:
**      along     double    unchanged
**      phi       double    unchanged
**      hm        double    unchanged
**      xpl       double    unchanged
**      ypl       double    unchanged
**      sphi      double    unchanged
**      cphi      double    unchanged
**      diurab    double    unchanged
**      p         double    unchanged
**      tk        double    unchanged
**      rh        double    unchanged
**      tlr       double    unchanged
**      wl        double    unchanged
**      refa      double    unchanged
**      refb      double    unchanged
**      eral      double    "local" Earth rotation angle (radians)
**
**  Notes:
**
**  1  The utc argument is UTC expressed as an MJD.  This is,
**     strictly speaking, improper, because of leap seconds.  However,
**     as long as the delta UT and the UTC are consistent there are no
**     difficulties, except during a leap second.  In this case, the
**     start of the 61st second of the final minute should begin a new
**     MJD day and the old pre-leap delta UT should continue to be
**     used.  As the 61st second completes, the MJD should revert to
**     the start of the day as, simultaneously, the delta UTC changes
**     by one second to its post-leap new value.
**
**  2  The delta UT (UT1-UTC) is tabulated in IERS bulletins.  It
**     increases by exactly one second at the end of each UTC leap
**     second, introduced in order to keep delta UT within +/- 0.9s.
**
**  3  The "adjusted longitude" ioprms->along is the observer's
**     longitude plus the tiny quantity s' plus the small amount of ERA
**     that corresponds to the current UT1-UTC.
**
**  4  The "local Earth rotation angle" ioprms->eral is ERA plus the
**     adjusted longitude.
**
**  Called:  slaEra
**
**  Last revision:   11 August 2008
**
**  Copyright P.T.Wallace.  All rights reserved.
*/
{

   ioprms->eral = slaEra ( 0.0, utc ) + ioprms->along;

}
