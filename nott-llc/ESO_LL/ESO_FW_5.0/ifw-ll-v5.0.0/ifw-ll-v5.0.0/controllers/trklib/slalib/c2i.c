#include "TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaC2i ( double rc, double dc, double pr, double pd,
              double px, double rv, double date, double dx, double dy,
              double *ri, double *di )
/*
**  - - - - - - -
**   s l a C 2 i
**  - - - - - - -
**
**  Transform ICRS star data, epoch J2000, to RA,Dec in the celestial
**  intermediate reference system.
**
**  Given:
**     rc,dc  double    ICRS RA,Dec at J2000 (radians)
**     pr,pd  double    proper motions:  RA,Dec changes per Julian year
**     px     double    parallax (arcsec)
**     rv     double    radial velocity (km/sec, +ve if receding)
**     date   double    TDB for CIRS place (JD-2400000.5)
**     dx,dy  double    corrections to IAU CIP X,Y (radians)
**
**  Returned:
**     ri,di  double*   CIRS RA,Dec (radians)
**
**  Notes:
**
**  1)  Star data for an epoch other than J2000 (for example from the
**      Hipparcos catalog) will require a preliminary call to slaPm
**      before use.
**
**  2)  The distinction between the required TDB and TT is always
**      negligible.  Moreover, for all but the most critical
**      applications, UTC is adequate.
**
**  3)  The proper motions in RA are dRA/dt rather than cos(Dec)*dRA/dt.
**
**  4)  This function may be wasteful for some applications because it
**      recomputes the Earth position/velocity and the bias-precession-
**      nutation matrix each time, and because it allows for parallax
**      and proper motion.  Where multiple transformations are to be
**      carried out for one date, a faster method is to call the
**      slaC2ipa function once and then either the slaC2iqk function
**      (which includes parallax and proper motion) or slaC2iqkz (which
**      assumes zero parallax and proper motion).
**
**  5)  The accuracy is sub-milliarcsecond, limited by the precession-
**      nutation information (IAU 2006 model plus the CIP corrections,
**      which are obtained from IERS bulletins).
**
**  6)  The accuracy is in principle further limited by the function
**      slaEpv, called by slaC2ipa, which computes the Earth position
**      and velocity.  The maximum error arising from this source is
**      less than 5 microarcseconds.
**
**  Called:  slaC2ipa, slaC2iqk
**
**  Last revision:   17 January 2006
**
**  Copyright P.T.Wallace.  All rights reserved.
*/
{
   CIpars ciprms;
   double eo;


/* Star-independent parameters. */
   slaC2ipa ( date, dx, dy, &ciprms, &eo );

/* ICRS (epoch J2000) to CIRS. */
   slaC2iqk ( rc, dc, pr, pd, px, rv, &ciprms, ri, di );

}
