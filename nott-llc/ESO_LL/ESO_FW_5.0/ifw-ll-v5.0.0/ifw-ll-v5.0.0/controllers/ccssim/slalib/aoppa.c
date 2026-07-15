#include "TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaAoppa ( double date, double dut, double elongm, double phim,
                double hm, double xp, double yp, double tk,
                double phpa, double rh, double wlfq, double tlr,
                double aoprms[14] )
/*
**  - - - - - - - - -
**   s l a A o p p a
**  - - - - - - - - -
**
**  Precompute apparent to observed place parameters required by
**  slaAopqk and slaOapqk.
**
**  Given:
**     date   d      UTC date/time (Modified Julian Date, JD-2400000.5)
**     dut    d      delta UT:  UT1-UTC (UTC seconds)
**     elongm d      mean longitude of the observer (radians, east +ve)
**     phim   d      mean geodetic latitude of the observer (radians)
**     hm     d      observer's height above sea level (metres)
**     xp     d      polar motion x-coordinate (radians)
**     yp     d      polar motion y-coordinate (radians)
**     tk     d      ambient temperature at the observer (K)
**     phpa   d      pressure at the observer (hPa = millibar)
**     rh     d      relative humidity at the observer (range 0-1)
**     wlfq   d      wavelength (micron) or minus frequency (GHz)
**     tlr    d      tropospheric lapse rate (K/metre, e.g. 0.0065)
**
**  Returned:
**     aoprms d[14]  star-independent apparent-to-observed parameters:
**
**       (0)      geodetic latitude (radians)
**       (1,2)    sine and cosine of geodetic latitude
**       (3)      magnitude of diurnal aberration vector
**       (4)      height (hm)
**       (5)      temperature (tk)
**       (6)      pressure (hPa)
**       (7)      relative humidity (rh)
**       (8)      wavelength or minus frequency (wlfq)
**       (9)      lapse rate (tlr)
**       (10,11)  refraction constants A and B (radians)
**       (12)     longitude + eqn of equinoxes + sidereal DUT (radians)
**       (13)     local apparent sidereal time (radians)
**
**  Notes:
**
**   1)  It is advisable to take great care with units, as even
**       unlikely values of the input parameters are accepted and
**       processed in accordance with the models used.
**
**   2)  The date argument is UTC expressed as an MJD.  This is,
**       strictly speaking, improper, because of leap seconds.  However,
**       as long as the delta UT and the UTC are consistent there
**       are no difficulties, except during a leap second.  In this
**       case, the start of the 61st second of the final minute should
**       begin a new MJD day and the old pre-leap delta UT should
**       continue to be used.  As the 61st second completes, the MJD
**       should revert to the start of the day as, simultaneously,
**       the delta UTC changes by one second to its post-leap new value.
**
**   3)  The delta UT (UT1-UTC) is tabulated in IERS circulars and
**       elsewhere.  It increases by exactly one second at the end of
**       each UTC leap second, introduced in order to keep delta UT
**       within +/- 0.9 seconds.
**
**   4)  IMPORTANT -- TAKE CARE WITH THE LONGITUDE SIGN CONVENTION.
**       The longitude required by the present function is
**       east-positive in accordance with geographical convention (and
**       right-handed).  In particular, note that the longitudes
**       returned by the slaObs function are west-positive, following
**       astronomical usage, and must be reversed in sign before use in
**       the present function.
**
**   5)  The polar coordinates xp,yp can be obtained from IERS
**       circulars and equivalent publications.  The maximum amplitude
**       is about 0.3 arcseconds.  If xp,yp values are unavailable,
**       use xp=yp=0.0.  See page B60 of the 1988 Astronomical Almanac
**       for a definition of the two angles.
**
**   6)  The height above sea level of the observing station, hm,
**       can be obtained from the Astronomical Almanac (Section J
**       in the 1988 edition), or via the function slaObs.  If p,
**       the pressure in hPa (millibars), is available, an adequate
**       estimate of hm can be obtained from the expression
**
**             hm = -29.3 * tsl * log ( p / 1013.25 );
**
**       where tsl is the approximate sea-level air temperature in K
**       (See Astrophysical Quantities, C.W.Allen, 3rd edition, section
**       52).  Similarly, if the pressure p is not known, it can be
**       estimated from the height of the observing station, hm, as
**       follows:
**
**             p = 1013.25 * exp ( -hm / ( 29.3 * tsl ) );
**
**       Note, however, that the refraction is nearly proportional to
**       the pressure and that an accurate p value is important for
**       precise work.
**
**   7)  Repeated, computationally-expensive, calls to slaAoppa for
**       times that are very close together can be avoided by calling
**       slaAoppa just once and then using slaAoppat for the subsequent
**       times.  Fresh calls to slaAoppa will be needed only when
**       changes in the equation of the equinoxes or the polar motion
**       have grown to unacceptable levels or when anything affecting
**       the refraction has changed.
**
**   8)  The argument wlfq specifies whether the refraction corrections
**       are for the optical or radio, and the wavelength/frequency.
**       Positive values specify wavelength in microns and are the usual
**       way of selecting the optical case.  Negative values specify
**       frequency in GHz and are the usual way of selecting the radio
**       case.  The transition from optical to radio is assumed to occur
**       at 100 microns (about 3000 GHz).
**
**  Defined in slamac.h:  D2PI, DS2R
**
**  Called:  slaGeoc, slaRefco, slaEqeqx, slaAoppat
**
**  Last revision:   13 August 2008
**
**  Copyright P.T.Wallace.  All rights reserved.
*/

#define C      173.14463331    /* Speed of light (AU per day) */
#define SOLSID 1.00273790935   /* Ratio between solar and sidereal time */

{
   double cphim, xt, yt, zt, xc, yc, zc, elong, phi, uau, vau;


/* Observer's location corrected for polar motion */
   cphim = cos_( phim );
   xt = cos_ ( elongm ) * cphim;
   yt = sin_ ( elongm ) * cphim;
   zt = sin_ ( phim );
   xc = xt - xp * zt;
   yc = yt + yp * zt;
   zc = xp * xt - yp * yt + zt;

   elong = ( xc != 0.0 || yc != 0.0 ) ? atan2_ ( yc, xc ) : 0.0;

   phi = atan2_ ( zc, sqrt_ ( xc * xc + yc * yc ) );
   aoprms[0] = phi;
   aoprms[1] = sin_ ( phi );
   aoprms[2] = cos_ ( phi );

/* Magnitude of the diurnal aberration vector */
   slaGeoc ( phi, hm, &uau, &vau );
   aoprms[3] = D2PI * uau * SOLSID / C;

/* Copy the refraction parameters and compute the A & B constants */
   aoprms[4] = hm;
   aoprms[5] = tk;
   aoprms[6] = phpa;
   aoprms[7] = rh;
   aoprms[8] = wlfq;
   aoprms[9] = tlr;
   slaRefco ( hm, tk, phpa, rh, wlfq, phi, tlr, 1e-10,
              &aoprms[10], &aoprms[11] );

/* Longitude + equation of the equinoxes + sidereal equivalent of DUT */
   aoprms[12] = elong + slaEqeqx ( date ) + dut * SOLSID * DS2R;

/* Sidereal time */
   slaAoppat ( date, aoprms );
}
