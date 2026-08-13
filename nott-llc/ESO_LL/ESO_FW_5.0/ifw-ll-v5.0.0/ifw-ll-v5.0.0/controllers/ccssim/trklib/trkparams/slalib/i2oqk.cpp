#include "../TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaI2oqk ( double ri, double di, IOpars *ioprms,
                double *aob, double *zob,
                double *hob, double *dob, double *rob )
/*
**  - - - - - - - - -
**   s l a I 2 o q k
**  - - - - - - - - -
**
**  Quick CIRS to observed place (but see Note 8, below, for remarks
**  about speed).
**
**  Given:
**     ri     double    CIRS right ascension
**     di     double    CIRS declination
**     ioprms IOpars*   star-independent CIRS-to-observed parameters:
**      along     double    longitude + s' + dERA(dut) (radians)
**      phi       double    geodetic latitude (radians)
**      hm        double    height above sea level (metres)
**      xpl       double    polar motion xp wrt local meridian (radians)
**      ypl       double    polar motion yp wrt local meridian (radians)
**      sphi      double    sine and cosine of geodetic latitude
**      cphi      double    sine and cosine of geodetic latitude
**      diurab    double    magnitude of diurnal aberration vector
**      p         double    pressure (mb,hPa)
**      tk        double    ambient temperature (K)
**      rh        double    relative humidity (0-1)
**      tlr       double    tropospheric lapse rate (K per metre)
**      wl        double    wavelength (micron) or minus frequency (GHz)
**      refa      double    refraction constant A (radians)
**      refb      double    refraction constant B (radians)
**      eral      double    "local" Earth Rotation Angle (radians)
**
**  Returned:
**     aob    double    observed azimuth (radians: N=0,E=90)
**     zob    double    observed zenith distance (radians)
**     hob    double    observed hour angle (radians)
**     dob    double    observed declination (radians)
**     rob    double    observed right ascension (CEO-based, radians)
**
**  Notes:
**
**   1)  This function returns zenith distance rather than elevation
**       in order to reflect the fact that no allowance is made for
**       depression of the horizon.
**
**   2)  The accuracy of the result is limited by the corrections for
**       refraction.  Providing the meteorological parameters are known
**       accurately and there are no gross local effects, the predicted
**       observed RA,Dec should be within about 0.1 arcsec for a zenith
**       distance of less than 70 degrees.  Even at a topocentric zenith
**       distance of 90 degrees, the accuracy in elevation should be
**       better than 1 arcmin;  useful results are available a little
**       lower still, beyond which the slaRefro function (q.v.) returns
**       a fixed value of the refraction.
**
**       The complementary functions slaI2o (or slaI2oqk) and slaO2i
**       (or slaO2iqk) are self-consistent to better than 1 micro-
**       arcsecond all over the celestial sphere.
**
**   3)  It is advisable to take great care with units, as even
**       unlikely values of the input parameters are accepted and
**       processed in accordance with the models used.
**
**   4)  The CIRS RA,Dec is obtained from a star catalogue mean place by
**       allowing for space motion, parallax, the Sun's gravitational
**       lens effect, annual aberration and precession-nutation.  For
**       star positions in the ICRS, these effects can be applied by
**       means of the slaC2i (etc.) functions.  Starting from the
**       formerly used "mean place" systems, additional transformations
**       will be needed first.
**
**   5)  "Observed" Az,El means the position that would be seen by a
**       perfect theodolite located at the observer.  This is obtained
**       from the CIRS RA,Dec by allowing for Earth orientation and
**       diurnal aberration, rotating from equator to horizon
**       coordinates, and then adjusting for refraction.  The HA,Dec is
**       obtained by rotating back into equatorial coordinates, and is
**       the position that would be seen by a perfect equatorial located
**       at the observer and with its polar axis aligned to the Earth's
**       axis of rotation (n.b. not to the refracted pole).  Finally,
**       the RA is obtained by subtracting the HA from the local ERA.
**
**   6)  To predict the required setting of a real telescope, the
**       observed place produced by this function would have to be
**       adjusted for the tilt of the azimuth or polar axis of the
**       mounting (with appropriate corrections for mount flexures),
**       for the non-perpendicularities between the two mount axes and
**       between the reference pointing axis and the mount declination
**       or elevation axis, for the desired image location in the focal
**       plane, for tube flexure, for gear and encoder errors, and
**       finally for encoder zero points.  Some telescopes would, of
**       course, exhibit other properties which would need to be
**       accounted for at the appropriate point in the sequence.
**
**   7)  The star-independent CIRS-to-observed-place parameters in
**       ioprms may be computed by means of the slaI2opa function.  If
**       nothing has changed significantly except the time, the
**       slaI2opat function may be used to perform the requisite partial
**       recomputation of ioprms.
**
**   8)  At zenith distances beyond about 76 degrees, the need for
**       special care with the corrections for refraction causes a
**       marked increase in execution time.  Moreover, the effect
**       gets worse with increasing zenith distance.  Adroit
**       programming in the calling application may allow the
**       problem to be reduced.  Prepare an alternative ioprms
**       structure, computed for zero air-pressure;  this will disable
**       the refraction corrections and cause rapid execution.  Using
**       this ioprms structure, a preliminary call to the present
**       function will, depending on the application, produce a rough
**       position which may be enough to establish whether the full,
**       slow calculation (using the real ioprms structure) is
**       worthwhile.  For example, there would be no need for the full
**       calculation if the preliminary call had already established
**       that the source was well below the elevation limits for a
**       particular telescope or antenna.
**
**  Called:  slaDcs2c,  slaRefz,  slaRefro,  slaDcc2s,  slaDranrm
**
**  Last revision:   17 May 2009
**
**  Copyright P.T.Wallace.  All rights reserved.
*/

/* Breakpoint for fast/slow refraction algorithm:       */
/* ZD greater than arctan(4), (see slaRefco function)   */
/* or vector Z less than cosine(arctan(Z)) = 1/sqrt(17) */
#define ZBREAK 0.242535625

{
   int i;
   double v[3], x, y, z, xhd, yhd, zhd, f, xhdt, yhdt, zhdt,
          xaet, yaet, zaet, azobs, zdt, zdobs, dzd, dref,
          ce, xaeo, yaeo, zaeo, hmobs, dcobs, raobs;



/* CIRS RA,Dec to Cartesian -HA,Dec. */
   slaDcs2c ( ri - ioprms->eral, di, v  );
   x = v[0];
   y = v[1];
   z = v[2];

/* Polar motion. */
   xhd = x + ioprms->xpl * z;
   yhd = y - ioprms->ypl * z;
   zhd = z - ioprms->xpl * x + ioprms->ypl * y;

/* Diurnal aberration. */
   f = ( 1.0 - ioprms->diurab * yhd );
   xhdt = f * xhd;
   yhdt = f * ( yhd + ioprms->diurab );
   zhdt = f * zhd;

/* Cartesian -HA,Dec to Cartesian Az,El (S=0,E=90). */
   xaet = ioprms->sphi * xhdt - ioprms->cphi * zhdt;
   yaet = yhdt;
   zaet = ioprms->cphi * xhdt + ioprms->sphi * zhdt;

/* Azimuth (N=0,E=90). */
   azobs = ( xaet != 0.0 || yaet != 0.0 ) ? atan2_ ( yaet, -xaet ) : 0.0;

/* Topocentric zenith distance. */
   zdt = atan2_ ( sqrt_ ( xaet * xaet + yaet * yaet ), zaet );

/* ---------- */
/* Refraction */
/* ---------- */

/* Fast algorithm using two constant model. */
   slaRefz ( zdt, ioprms->refa, ioprms->refb, &zdobs );

/* If large zenith distance, use rigorous algorithm. */
   if ( cos_ ( zdobs ) < ZBREAK ) {

   /* Loop (maximum of 10 iterations). */
      i = 1;
      do {

      /* Compute refraction using current estimate of observed ZD. */
         slaRefro ( zdobs,
                    ioprms->hm, ioprms->tk, ioprms->p, ioprms->rh,
                    ioprms->wl, ioprms->phi, ioprms->tlr, 1e-8,
                    &dref );

      /* Remaining discrepancy. */
         dzd = zdobs + dref - zdt;

      /* Update the estimate. */
         zdobs -= dzd;

      /* Increment the iteration counter. */
         i++;

      } while ( fabs_ ( dzd ) > 1e-10 && i <= 10 );
   }

/* To Cartesian Az/ZD. */
   ce = sin_ ( zdobs );
   xaeo = - cos_ ( azobs ) * ce;
   yaeo = sin_ ( azobs ) * ce;
   zaeo = cos_ ( zdobs );

/* Cartesian Az/ZD to Cartesian -HA,Dec. */
   v[0] = ioprms->sphi * xaeo + ioprms->cphi * zaeo;
   v[1] = yaeo;
   v[2] =  - ioprms->cphi * xaeo + ioprms->sphi * zaeo;

/* To spherical -HA,Dec. */
   slaDcc2s ( v, &hmobs, &dcobs );

/* Right ascension (with respect to CEO). */
   raobs = slaDranrm ( ioprms->eral + hmobs );

/* Return the results. */
   *aob = azobs;
   *zob = zdobs;
   *hob = -hmobs;
   *dob = dcobs;
   *rob = raobs;

}
