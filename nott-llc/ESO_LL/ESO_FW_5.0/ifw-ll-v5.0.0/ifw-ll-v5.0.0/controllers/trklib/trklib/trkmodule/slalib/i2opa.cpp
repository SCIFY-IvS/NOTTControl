#include "../TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaI2opa ( double utc, double dut, double elong, double phi,
                double hm, double xp, double yp, double tk, double phpa,
                double rh, double wlfq, double tlr, IOpars *ioprms )
/*
**  - - - - - - - - -
**   s l a I 2 o p a
**  - - - - - - - - -
**
**  Precompute CIRS to observed place parameters required by slaI2oqk
**  and slaO2iqk.
**
**  Given:
**     utc    double    UTC date/time (MJD, JD-2400000.5)
**     dut    double    delta UT:  UT1-UTC (UTC seconds)
**     elong  double    longitude of the observer (radians, east +ve)
**     phi    double    geodetic latitude of the observer (radians)
**     hm     double    observer's height above sea level (meters)
**     xp     double    polar motion x-coordinate (radians)
**     yp     double    polar motion y-coordinate (radians)
**     tk     double    ambient temperature at the observer (K)
**     phpa   double    pressure at the observer (hPa = millibar)
**     rh     double    relative humidity at the observer (range 0-1)
**     wlfq   double    wavelength (micron) or minus frequency (GHz)
**     tlr    double    tropospheric lapse rate (K/m, e.g. 0.0065)
**
**  Returned:
**     ioprms IOpars*   star-independent CIRS-to-observed parameters:
**      along     double    longitude + s' + dERA(dut) (radians)
**      phi       double    geodetic latitude (radians)
**      hm        double    height above sea level (meters)
**      xpl       double    polar motion xp wrt local meridian (radians)
**      ypl       double    polar motion yp wrt local meridian (radians)
**      sphi      double    sine of geodetic latitude
**      cphi      double    cosine of geodetic latitude
**      diurab    double    magnitude of diurnal aberration vector
**      p         double    pressure (hPa, mb)
**      tk        double    ambient temperature (K)
**      rh        double    relative humidity (0-1)
**      tlr       double    tropospheric lapse rate (K per meter)
**      wl        double    wavelength (micron) or minus frequency (GHz)
**      refa      double    refraction constant A (radians)
**      refb      double    refraction constant B (radians)
**      eral      double    "local" Earth Rotation Angle (radians)
**
**  Notes:
**
**   1) It is advisable to take great care with units, as even unlikely
**      values of the input parameters are accepted and processed in
**      accordance with the models used.
**
**   2) The utc argument is UTC expressed as an MJD.  This is,
**      strictly speaking, improper, because of leap seconds.  However,
**      as long as the delta UT and the UTC are consistent there are no
**      difficulties, except during a leap second.  In this case, the
**      start of the 61st second of the final minute should begin a new
**      MJD day and the old pre-leap delta UT should continue to be
**      used.  As the 61st second completes, the MJD should revert to
**      the start of the day as, simultaneously, the delta UTC changes
**      by one second to its post-leap new value.
**
**   3) The delta UT (UT1-UTC) is tabulated in IERS bulletins.  It
**      increases by exactly one second at the end of each UTC leap
**      second, introduced in order to keep delta UT within +/- 0.9s.
**
**   4) IMPORTANT -- TAKE CARE WITH THE LONGITUDE SIGN CONVENTION.
**      The longitude required by the present function is east-positive,
**      in accordance with geographical convention (and right-handed).
**      In particular, note that the longitudes returned by the
**      slaObs function are west-positive, following astronomical
**      usage, and must be reversed in sign before use in the present
**      function.
**
**   5) The polar motion coordinates xp,yp can be obtained from IERS
**      bulletins.  The maximum amplitude is about 0.3 arcseconds.  If
**      xp,yp values are unavailable, use zeroes.  The xp,yp
**      coordinates are reckoned as follows:
**
**      . +ve xp means that the point on the geoid directly beneath
**        the CIP is in the hemisphere centered on longitude 90 deg.
**
**      . +ve yp means that the point on the geoid directly beneath
**        the CIP is in the hemisphere centered on longitude 270 deg.
**
**      Internally, the polar motion is stored in a form rotated onto
**      the local meridian.
**
**   6) The height above sea level of the observing station, hm, can be
**      obtained from the Astronomical Almanac (Section J in the 1988
**      edition), or via the function slaObs.  If p, the pressure in
**      hPa (millibars), is available, an adequate estimate of hm can be
**      obtained from the expression
**
**            hm = -29.3 * tsl * log ( p / 1013.25 );
**
**      where tsl is the approximate sea-level air temperature in K
**      (See Astrophysical Quantities, C.W.Allen, 3rd edition, section
**      52).  Similarly, if the pressure p is not known, it can be
**      estimated from the height of the observing station, hm, as
**      follows:
**
**            p = 1013.25 * exp ( -hm / ( 29.3 * tsl ) );
**
**      Note, however, that the refraction is nearly proportional to
**      the pressure and that an accurate p value is important for
**      precise work.
**
**   7) The "adjusted longitude" ioprms->along is the observer's
**      longitude plus the tiny quantity s' plus the small amount of ERA
**      that corresponds to the current UT1-UTC.
**
**   8) The "local Earth rotation angle" ioprms->eral is ERA plus the
**      adjusted longitude.
**
**   9) Repeated, computationally-expensive, calls to slaI2opa for
**      times that are very close together can be avoided by calling
**      slaI2opa just once and then using slaI2opat for the subsequent
**      times.  Fresh calls to slaI2opa will be needed only when changes
**      in the polar motion have grown to unacceptable levels or when
**      anything affecting the refraction has changed.
**
**  10) The argument wlfq specifies whether the refraction corrections
**      are for the optical or radio, and the wavelength/frequency.
**      Positive values specify wavelength in microns and are the usual
**      way of selecting the optical case.  Negative values specify
**      frequency in GHz and are the usual way of selecting the radio
**      case.  The transition from optical to radio is assumed to occur
**      at 100 microns (about 3000 GHz).
**
**  Defined in slamac.h:  D2PI, DS2R
**
**  Called:  slaSp, slaGeoc, slaRefco, slaI2opat
**
**  Last revision:   11 August 2008
**
**  Copyright P.T.Wallace.  All rights reserved.
*/

#define C 173.14463331  /* speed of light (AU per day) */
#define SOLSID 1.00273781191135448  /* ratio between UT1 and ERA */

{
   double sl, cl, uau, vau;


/* Longitude with adjustments s' and dERA(DUT) (radians). */
   ioprms->along = elong + slaSp ( utc ) + dut * SOLSID * DS2R;

/* Latitude. */
   ioprms->phi = phi;

/* Height. */
   ioprms->hm = hm;

/* Polar motion, rotated onto the local meridian. */
   sl = sin_( elong );
   cl = cos_( elong );
   ioprms->xpl = xp * cl  -  yp * sl;
   ioprms->ypl = xp * sl  +  yp * cl;

/* Functions of latitude. */
   ioprms->sphi = sin_ ( phi );
   ioprms->cphi = cos_ ( phi );

/* Magnitude of the diurnal aberration vector. */
   slaGeoc ( phi, hm, &uau, &vau );
   ioprms->diurab = D2PI * uau * SOLSID / C;

/* Refraction parameters. */
   ioprms->p = phpa;
   ioprms->tk = tk;
   ioprms->rh = rh;
   ioprms->tlr = tlr;
   ioprms->wl = wlfq;

/* Compute the A & B refraction constants. */
   slaRefco ( ioprms->hm, ioprms->tk, ioprms->p, ioprms->rh,
              ioprms->wl, ioprms->phi, ioprms->tlr, 1e-10,
              &ioprms->refa, &ioprms->refb );

/* Earth rotation angle. */
   slaI2opat ( utc, ioprms );

}
