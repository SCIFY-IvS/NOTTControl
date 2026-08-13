#include "../TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaI2o ( double ri, double di, double date, double dut,
              double elong, double phi, double hm, double xp, double yp,
              double tk, double phpa, double rh, double wlfq,
              double tlr, double *aob, double *zob, double *hob,
              double *dob, double *rob )
/*
**  - - - - - - -
**   s l a I 2 o
**  - - - - - - -
**
**  CIRS RA,Dec to observed place at a ground based site, for sources
**  distant from the solar system.
**
**  Given:
**     ri    double   CIRS right ascension (CEO-based, radians)
**     di    double   CIRS declination (radians)
**     date  double   UTC date/time (Modified Julian Date, JD-2400000.5)
**     dut   double   delta UT:  UT1-UTC (UTC seconds)
**     elong double   longitude of the observer (radians, east +ve)
**     phi   double   geodetic latitude of the observer (radians)
**     hm    double   observer's height above sea level (metres)
**     xp    double   polar motion x-coordinate (radians)
**     yp    double   polar motion y-coordinate (radians)
**     tk    double   ambient temperature at the observer (K)
**     phpa  double   pressure at the observer (hPa = millibar)
**     rh    double   relative humidity at the observer (range 0-1)
**     wlfq  double   wavelength (micron) or minus frequency (GHz)
**     tlr   double   tropospheric lapse rate (K/metre, e.g. 0.0065)
**
**  Returned:
**     aob   double*  observed azimuth (radians: N=0,E=90)
**     zob   double*  observed zenith distance (radians)
**     hob   double*  observed hour angle (radians)
**     dob   double*  observed declination (radians)
**     rob   double*  observed right ascension (CEO-based, radians)
**
**  Notes:
**
**   1) This function returns zenith distance rather than elevation
**      in order to reflect the fact that no allowance is made for
**      depression of the horizon.
**
**   2) The accuracy of the result is limited by the corrections for
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
**   3) It is advisable to take great care with units, as even
**      unlikely values of the input parameters are accepted and
**      processed in accordance with the models used.
**
**   4) The CIRS RA,Dec is obtained from a star catalogue mean place by
**      allowing for space motion, parallax, the Sun's gravitational
**      lens effect, annual aberration and precession-nutation.  For
**      star positions in the ICRS, these effects can be applied by
**      means of the slaC2i etc. functions.  Starting from the
**      formerly used "mean place" systems, additional transformations
**      will be needed first.
**
**   5) "Observed" Az,ZD means the position that would be seen by a
**      perfect theodolite located at the observer.  This is obtained
**      from the CIRS RA,Dec by allowing for Earth orientation and
**      diurnal aberration, rotating from equator to horizon
**      coordinates, and then adjusting for refraction.  The HA,Dec is
**      obtained by rotating back into equatorial coordinates, and is
**      the position that would be seen by a perfect equatorial located
**      at the observer and with its polar axis aligned to the Earth's
**      axis of rotation (n.b. not to the refracted pole).  Finally,
**      the RA is obtained by subtracting the HA from the local ERA.
**
**   6) To predict the required setting of a real telescope, the
**      observed place produced by this function would have to be
**      adjusted for the tilt of the azimuth or polar axis of the
**      mounting (with appropriate corrections for mount flexures),
**      for the non-perpendicularities between the two mount axes and
**      between the reference pointing axis and the mount declination
**      or elevation axis, for the desired image location in the focal
**      plane, for tube flexure, for gear and encoder errors, and
**      finally for encoder zero points.  Some telescopes would, of
**      course, exhibit other properties which would need to be
**      accounted for at the appropriate point in the sequence.
**
**   7) This function takes time to execute, due mainly to the
**      rigorous ray-trace integration used to evaluate the refraction.
**      For processing multiple stars for one location and time, call
**      slaI2opa once followed by one call per star to slaI2oqk.
**      Where a range of times within a limited period of a few hours
**      is involved, and the highest precision is not required, call
**      slaI2opa once, followed by a call to slaI2opat each time the
**      time changes, followed by one call per star to slaI2oqk.
**
**   8) The date argument is UTC expressed as an MJD.  This is,
**      strictly speaking, improper, because of leap seconds.  However,
**      as long as the delta UT and the UTC are consistent there are no
**      difficulties, except during a leap second.  In this case, the
**      start of the 61st second of the final minute should begin a new
**      MJD day and the old pre-leap delta UT should continue to be
**      used.  As the 61st second completes, the MJD should revert to
**      the start of the day as, simultaneously, the delta UTC changes
**      by one second to its post-leap new value.
**
**   9) The delta UT (UT1-UTC) is tabulated in IERS bulletins.  It
**      increases by exactly one second at the end of each UTC leap
**      second, introduced in order to keep delta UT within +/- 0.9s.
**
**  10) IMPORTANT -- TAKE CARE WITH THE LONGITUDE SIGN CONVENTION.
**      The longitude required by the present function is east-positive,
**      in accordance with geographical convention (and right-handed).
**      In particular, note that the longitudes returned by the
**      slaObs function are west-positive, following astronomical
**      usage, and must be reversed in sign before use in the present
**      function.
**
**  11) The polar motion coordinates xp,yp can be obtained from IERS
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
**  12) The height above sea level of the observing station, hm,
**      can be obtained from the Astronomical Almanac (Section J
**      in the 1988 edition), or via the function slaObs.  If p,
**      the pressure in hPa (millibars), is available, an adequate
**      estimate of hm can be obtained from the expression
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
**  13) The argument wlfq specifies whether the refraction corrections
**      are for the optical or radio, and the wavelength/frequency.
**      Positive values specify wavelength in microns and are the usual
**      way of selecting the optical case.  Negative values specify
**      frequency in GHz and are the usual way of selecting the radio
**      case.  The transition from optical to radio is assumed to occur
**      at 100 microns (about 3000 GHz).
**
**  Called:  slaI2opa, slaI2oqk
**
**  Last revision:   17 May 2009
**
**  Copyright P.T.Wallace.  All rights reserved.
*/

{
   IOpars ioprms;


   slaI2opa ( date, dut, elong, phi, hm, xp, yp, tk, phpa, rh, wlfq,
              tlr, &ioprms );
   slaI2oqk ( ri, di, &ioprms, aob, zob, hob, dob, rob );

}
