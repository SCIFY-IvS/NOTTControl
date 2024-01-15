#include "TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaO2iqk ( const char *type,
                double ob1, double ob2, IOpars *ioprms,
                double *ri, double *di )
/*
**  - - - - - - - - -
**   s l a O 2 i q k
**  - - - - - - - - -
**
**  Quick observed place to CIRS:  observed place at a ground based site
**  to CIRS RA,Dec, for sources distant from the solar system, given the
**  star-independent CIRS-to-observed parameters.
**
**  Given:
**     type   char[]    type of coordinates: 'R', 'H' or 'A' (see below)
**     ob1    double    observed Az, HA or RA (radians; Az is N=0,E=90)
**     ob2    double    observed ZD or Dec (radians)
**     ioprms IOpars*   star-independent CIRS-to-observed parameters:
**      along     double    longitude + s' + dERA(DUT) (radians)
**      phi       double    geodetic latitude (radians)
**      hm        double    height above sea level (meters)
**      xpl       double    polar motion xp wrt local meridian (radians)
**      ypl       double    polar motion yp wrt local meridian (radians)
**      sphi      double    sine and cosine of geodetic latitude
**      cphi      double    sine and cosine of geodetic latitude
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
**  Returned:
**     ri     double*   CIRS right ascension (CEO-based, radians)
**     di     double*   CIRS declination (radians)
**
**  Notes:
**
**  1)  Only the first character of the type argument is significant.
**      "R" or "r" indicates that ob1 and ob2 are the observed right
**      ascension and declination;  "H" or "h" indicates that they are
**      hour angle (west +ve) and declination;  anything else ("A" or
**      "a" is recommended) indicates that ob1 and ob2 are azimuth
**      (north zero, east 90 deg) and zenith distance.  (Zenith
**      distance is used rather than elevation in order to reflect the
**      fact that no allowance is made for depression of the horizon.)
**
**  2)  The accuracy of the result is limited by the corrections for
**      refraction.  Providing the meteorological parameters are known
**      accurately and there are no gross local effects, the predicted
**      observed RA,Dec should be within about 0.1 arcsec for a zenith
**      distance of less than 70 degrees.  Even at a topocentric zenith
**      distance of 90 degrees, the accuracy in elevation should be
**      better than 1 arcmin;  useful results are available a little
**      lower still, beyond which the slaRefro function (q.v.) returns
**      a fixed value of the refraction.
**
**      The complementary functions slaI2o (or slaI2oqk) and slaO2i
**      (or slaO2iqk) are self-consistent to better than 1 micro-
**      arcsecond all over the celestial sphere.
**
**  3)  It is advisable to take great care with units, as even
**      unlikely values of the input parameters are accepted and
**      processed in accordance with the models used.
**
**  4)  "Observed" Az,El means the position that would be seen by a
**      perfect theodolite located at the observer.  This is
**      related to the observed HA,Dec via the standard rotation, using
**      the geodetic latitude (corrected for polar motion), while the
**      observed HA and RA are related simply through the Earth rotation
**      angle and the site longitude.  "Observed" RA,Dec or HA,Dec thus
**      means the position that would be seen by a perfect equatorial
**      located at the observer and with its polar axis aligned to the
**      Earth's axis of rotation (n.b. not to the refracted pole).  By
**      removing from the observed place the effects of atmospheric
**      refraction and diurnal aberration, the CIRS RA,Dec is obtained.
**
**  5)  Frequently, ICRS RA,Dec rather than CIRS RA,Dec will be
**      required, in which case further transformations will be
**      necessary.  The slaIbp etc. functions will convert the CIRS
**      RA,Dec produced by the present function into an ICRS astrometric
**      place, by allowing for the Sun's gravitational lens effect,
**      annual aberration and precession-nutation.
**
**  6)  To convert to CIRS RA,Dec the coordinates read from a real
**      telescope, corrections would have to be applied for encoder zero
**      points, gear and encoder errors, tube flexure, the position of
**      the rotator axis and the pointing axis relative to it, non-
**      perpendicularity between the mounting axes, and finally for the
**      tilt of the azimuth or polar axis of the mounting (with
**      appropriate corrections for mount flexures).  Some telescopes
**      would, of course, exhibit other properties which would need to
**      be accounted for at the appropriate point in the sequence.
**
**  7)  The star-independent CIRS-to-observed parameters in ioprms may
**      be computed by means of the slaI2opa function.  If nothing has
**      changed significantly except the time, the slaI2opat function
**      may be used to perform the requisite partial recomputation of
**      ioprms.
**
**  Called:  slaDcs2c, slaDcc2s, slaRefro, slaDranrm
**
**  Last revision:   17 May 2009
**
**  Copyright P.T.Wallace.  All rights reserved.
*/

/* Breakpoint for fast/slow refraction algorithm:       */
/* ZD greater than arctan(4), (see slaRefco function)    */
/* or vector Z less than cosine(arctan(Z)) = 1/sqrt(17) */
#define ZBREAK 0.242535625

{

   int c;
   double c1, c2, sphi, cphi, ce, xaeo, yaeo, zaeo, v[3],
          xmhdo, ymhdo, zmhdo, az, sz, zdo, refa, refb, tz, dref,
          zdt, xaet, yaet, zaet, xmhda, ymhda, zmhda,
          diurab, f, xhd, yhd, zhd, xpl, ypl, w, hma;



/* Coordinate type. */
   c = (int) type[0];

/* Coordinates. */
   c1 = ob1;
   c2 = ob2;

/* Sin, cos of latitude. */
   sphi = ioprms->sphi;
   cphi = ioprms->cphi;

/* Standardize coordinate type. */
   if ( c == 'r' || c == 'R' ) {
      c = 'R';
   } else if ( c == 'h' || c  == 'H' ) {
      c = 'H';
   } else {
      c = 'A';
   }

/* If Az,ZD convert to Cartesian (S=0,E=90). */
   if ( c == 'A' ) {
      ce = sin_( c2 );
      xaeo = - cos_( c1 ) * ce;
      yaeo = sin_( c1 ) * ce;
      zaeo = cos_( c2 );
   } else {

   /* If RA,Dec convert to HA,Dec. */
      if ( c == 'R' ) c1 = ioprms->eral - c1;

   /* To Cartesian -HA,Dec. */
      slaDcs2c ( -c1, c2, v );
      xmhdo = v[0];
      ymhdo = v[1];
      zmhdo = v[2];

   /* To Cartesian Az,El (S=0,E=90). */
      xaeo = sphi*xmhdo - cphi*zmhdo;
      yaeo = ymhdo;
      zaeo = cphi*xmhdo + sphi*zmhdo;
   }

/* Azimuth (S=0,E=90). */
   az = ( xaeo != 0.0 || yaeo != 0.0 ) ? atan2_ ( yaeo, xaeo ) : 0.0;
   
/* Sine of observed ZD, and observed ZD. */
   sz = sqrt_ ( xaeo*xaeo + yaeo*yaeo );
   zdo = atan2_ ( sz, zaeo );

/*
** Refraction
** ----------
*/

/* Large zenith distance? */
   if ( zaeo >= ZBREAK ) {

   /* Fast algorithm using two constant model. */
      refa = ioprms->refa;
      refb = ioprms->refb;
      tz = sz / zaeo;
      dref = ( refa + refb * tz * tz ) * tz;

   } else {

   /* Rigorous algorithm for large ZD. */
      slaRefro ( zdo,
                 ioprms->hm, ioprms->tk, ioprms->p, ioprms->rh,
                 ioprms->wl, ioprms->phi, ioprms->tlr, 1e-8,
                 &dref );
   }

   zdt = zdo + dref;

/* To Cartesian Az,ZD. */
   ce = sin_ ( zdt );
   xaet = cos_ ( az ) * ce;
   yaet = sin_ ( az ) * ce;
   zaet = cos_ ( zdt );

/* Cartesian Az,ZD to Cartesian -HA,Dec. */
   xmhda = sphi * xaet + cphi * zaet;
   ymhda = yaet;
   zmhda = - cphi * xaet + sphi * zaet;

/* Diurnal aberration. */
   diurab = - ioprms->diurab;
   f = ( 1.0 - diurab * ymhda );
   xhd = f * xmhda;
   yhd = f * ( ymhda + diurab );
   zhd = f * zmhda;

/* Polar motion. */
   xpl = ioprms->xpl;
   ypl = ioprms->ypl;
   w = xpl*xhd - ypl*yhd + zhd;
   v[0] = xhd - xpl*w;
   v[1] = yhd + ypl*w;
   v[2] = w - ( xpl*xpl + ypl*ypl ) * zhd;

/* To spherical -HA,Dec. */
   slaDcc2s ( v, &hma, di );

/* Right ascension. */
   *ri = slaDranrm ( ioprms->eral + hma );

}
