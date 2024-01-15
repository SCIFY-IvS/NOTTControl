#include "../TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaI2opad ( IOpars *ioprms )
/*
**  - - - - - - - - - -
**   s l a I 2 o p a d
**  - - - - - - - - - -
**
**  In the CIRS to observed place star-independent parameter structure,
**  disable the diurnal aberration.
**
**  Given:
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
**      along     double
**      phi       double
**      hm        double
**      xpl       double
**      ypl       double
**      sphi      double
**      cphi      double
**      diurab    double    set to zero
**      p         double
**      tk        double
**      rh        double
**      tlr       double
**      wl        double
**      refa      double
**      refb      double
**      eral      double
**
**  Notes:
**
**  1  This capability is provided to bypass the geocentric stage in the
**     transformation from ICRS to CIRS coordinates;  the site velocity
**     and position can be specified at that point.  One motivation for
**     doing so would be to include (stellar) geocentric parallax, which
**     is neglected in the slaI2o functions.
**
**  2  To re-instate the correction for diurnal aberration, use
**     slaI2opa.
**
**  3  For more information, see slaI2opa.
**
**  Last revision:   13 August 2008
**
**  Copyright P.T.Wallace.  All rights reserved.
*/
{

   ioprms->diurab = 0.0;

}
