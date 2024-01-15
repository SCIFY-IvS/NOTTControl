#include "../TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaC2ipa ( double date, double dx, double dy,
                CIpars *ciprms, double *eo )
/*
**  - - - - - - - - -
**   s l a C 2 i p a
**  - - - - - - - - -
**
**  For a geocentric observer, compute star-independent parameters in
**  preparation for conversions between ICRS star data CIRS RA,Dec.
**
**  The parameters produced by this function are required in the
**  parallax, light deflection, aberration and precession-nutation parts
**  of the ICRS/CIRS transformations.
**
**  Given:
**     date    double     TDB (JD-2400000.5)
**     dx,dy   double     corrections to IAU CIP X,Y (radians)
**
**  Returned:
**     ciprms  CIpars*    star-independent ICRS-to-CIRS parameters:
**      pmt        double    time interval for proper motion (Jyears)
**      eb[3]      double    SSB to Earth (AU)
**      ehn[3]     double    Sun to Earth unit vector
**      gr2e       double    (grav rad Sun)*2/(Sun-Earth distance)
**      abv[3]     double    barycentric Earth velocity in units of c
**      ab1        double    sqrt(1-v**2) where v=modulus(abv)
**      bpn[3][3]  double    bias-precession-nutation matrix
**     eo      double*    equation of the origins (ERA-GST)
**
**  Notes:
**
**  1)  For date, the distinction between the required TDB and TT is
**      always negligible.  Moreover, for all but the most critical
**      applications UTC is adequate.
**
**  2)  The vectors ciprms->eb and ciprms->ehn are in the BCRS.
**
**  3)  The parameters ciprms produced by this function are used by
**      slaC2iqk, slaC2iqkz and slaI2cqk.  The bias-precession-
**      nutation portion can be suppressed using slaC2ipad, allowing
**      transformations to and from GCRS instead of CIRS.
**
**  4)  The accuracy is sub-milliarcsecond, limited by the precession-
**      nutation information (IAU 2006 model plus the CIP corrections,
**      which are obtained from IERS bulletins).
**
**  5)  The accuracy is in principle further limited by the function
**      slaEpv, which computes the Earth position and velocity.  The
**      maximum error arising from this source is less than
**      5 microarcseconds.
**
**  Called:  slaC2ipas
**
**  Last revision:   18 January 2006
**
**  Copyright P.T.Wallace.  All rights reserved.
*/
{

/* Geocentric observer */
   double pv[2][3] = { { 0.0, 0.0, 0.0 }, { 0.0, 0.0, 0.0 } };



/* Compute the ICRS-to-CIRS star-independent parameters. */
   slaC2ipas ( date, pv, dx, dy, ciprms, eo );

}
