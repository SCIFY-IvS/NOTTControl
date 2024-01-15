#include "TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaI2c ( double ri, double di, double date, double dx, double dy,
              double *rc, double *dc )
/*
**  - - - - - - -
**   s l a I 2 c
**  - - - - - - -
**
**  Transform star RA,Dec from CIRS to ICRS astrometric.
**
**  Given:
**     ri,di     double    CIRS RA,Dec (radians)
**     date      double    TDB (JD-2400000.5)
**     dx,dy     double    corrections to IAU 2000A CIP X,Y (radians)
**
**  Returned:
**     rc,dc     double*   ICRS astrometric RA,Dec (radians)
**
**  Notes:
**
**  1)  The distinction between the required TDB and TT is always
**      negligible.  Moreover, for all but the most critical
**      applications UTC is adequate.
**
**  2)  Iterative techniques are used for the aberration and light
**      deflection corrections so that the functions slaI2c (or
**      slaI2cqk) and slaC2i (or slaC2iqk) are accurate inverses; even
**      at the edge of the Sun's disc the discrepancy is only about
**      1 nanoarcsecond.
**
**  3)  Where multiple CIRS RA,Decs are to be transformed into
**      astrometric places, for a fixed date, it is more efficient to
**      use the slaC2ipa function to compute the required parameters
**      once, followed by one call to slaI2cqk per star.
**
**  4)  The accuracy is sub-milliarcsecond, limited by the precession-
**      nutation information (IAU 2006 model plus the CIP corrections,
**      which are obtained from IERS bulletins).
**
**  5)  The accuracy is in principle further limited by the function
**      slaEpv, called by slaC2ipa, which computes the Earth position
**      and velocity.  The maximum error arising from this source is
**      less than 5 microarcseconds.
**
**  Reference:
**
**     Explanatory Supplement to the Astronomical Ephemeris, Chapter 3.
**
**  Called:  slaC2ipa, slaI2cqk
**
**  This revision:   17 January 2006
**
**  Copyright P.T.Wallace.  All rights reserved.
*/
{
   CIpars ciprms;
   double eo;



/* Star-independent parameters. */
   slaC2ipa ( date, dx, dy, &ciprms, &eo );

/* CIRS to ICRS astrometric. */
   slaI2cqk ( ri, di, &ciprms, rc, dc );

}
